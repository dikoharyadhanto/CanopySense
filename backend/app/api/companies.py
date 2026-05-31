import io
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

import asyncpg
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel

from app.api.admin.audit_log import log_admin_action
from app.api.deps import get_current_user
from app.auth.jwt import get_password_hash, verify_password
from app.database import get_db_pool, settings
from app.limiter import limiter
from app.services.email import send_viewer_invite_email
from app.services.spatial_validator import convert_to_geojson_bytes, validate_geojson_bytes

router = APIRouter()

VIEWER_INVITE_TTL_HOURS = 48
LOGO_MAX_BYTES = 2 * 1024 * 1024  # 2 MB
LOGO_MAX_HEIGHT = 48
LOGO_MAX_WIDTH = 200
ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/svg+xml"}
ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg"}
UPLOADS_BASE = Path(__file__).resolve().parent.parent.parent.parent / "uploads"


def _require_manager(current_user: dict, company_id: int) -> None:
    """Raises 403 if caller is not a manager of the given company."""
    if current_user.get("role") != "manager" or current_user.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail="Manager access required for this company")


def _require_manager_or_super_admin(current_user: dict, company_id: int) -> None:
    if current_user.get("role") == "super_admin":
        return
    _require_manager(current_user, company_id)


def _company_id_key(request: Request) -> str:
    company_id = request.path_params.get("company_id", "unknown")
    return f"company:{company_id}"


# ─── POST /companies/{company_id}/members/invite ──────────────────────────────

class InviteViewerRequest(BaseModel):
    email: str


@router.post("/{company_id}/members/invite", status_code=202)
@limiter.limit("10/day", key_func=_company_id_key)
async def invite_viewer(
    request: Request,
    company_id: int,
    body: InviteViewerRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager(current_user, company_id)

    async with pool.acquire() as conn:
        company = await conn.fetchrow(
            "SELECT id, company_name FROM companies WHERE id = $1", company_id
        )
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        existing = await conn.fetchrow(
            "SELECT id, company_id FROM users WHERE email = $1", body.email
        )
        if existing and existing["company_id"] is not None:
            raise HTTPException(status_code=409, detail="User already belongs to a company")

        plaintext = secrets.token_urlsafe(32)
        token_hash = get_password_hash(plaintext)
        expires_at = datetime.utcnow() + timedelta(hours=VIEWER_INVITE_TTL_HOURS)

        if existing:
            await conn.execute(
                """
                UPDATE users
                SET viewer_invite_token_hash = $1,
                    viewer_invite_token_expires_at = $2,
                    company_id = $3,
                    updated_at = NOW()
                WHERE id = $4
                """,
                token_hash, expires_at, company_id, existing["id"],
            )
        else:
            provisional_username = body.email.split("@")[0] + "_" + secrets.token_hex(4)
            await conn.execute(
                """
                INSERT INTO users (email, username, password_hash, company_id,
                                   viewer_invite_token_hash, viewer_invite_token_expires_at,
                                   is_active, setup_required)
                VALUES ($1, $2, $3, $4, $5, $6, TRUE, TRUE)
                """,
                body.email, provisional_username,
                get_password_hash(secrets.token_hex(16)),
                company_id, token_hash, expires_at,
            )

        await log_admin_action(
            conn, current_user["id"], "invite_viewer", "company", company_id,
            {"email": body.email},
        )

    invite_link = (
        f"{settings.FRONTEND_URL}/accept-invite?token={plaintext}"
    )
    try:
        await send_viewer_invite_email(body.email, company["company_name"], invite_link)
    except Exception:
        pass

    return {"message": "Invitation sent.", "expires_at": expires_at.isoformat()}


# ─── GET /companies/{company_id}/members ──────────────────────────────────────

@router.get("/{company_id}/members")
async def list_members(
    company_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager_or_super_admin(current_user, company_id)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, username, full_name, email, role, created_at AS joined_at,
                   leave_request_status
            FROM users
            WHERE company_id = $1 AND role IS NOT NULL
            ORDER BY created_at ASC
            """,
            company_id,
        )
    return {"members": [dict(r) for r in rows]}


# ─── DELETE /companies/{company_id}/members/{user_id} ────────────────────────

@router.delete("/{company_id}/members/{user_id}", status_code=200)
async def remove_member(
    company_id: int,
    user_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager(current_user, company_id)

    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    async with pool.acquire() as conn:
        target = await conn.fetchrow(
            "SELECT id, role, company_id FROM users WHERE id = $1 AND company_id = $2",
            user_id, company_id,
        )
        if not target:
            raise HTTPException(status_code=404, detail="Member not found in this company")

        if target["role"] in ("manager", "admin", "super_admin"):
            raise HTTPException(status_code=403, detail="Cannot remove managers or admin users")

        await conn.execute(
            """
            UPDATE users
            SET company_id = NULL, role = NULL, updated_at = NOW()
            WHERE id = $1
            """,
            user_id,
        )
        await log_admin_action(
            conn, current_user["id"], "remove_member", "user", user_id,
            {"company_id": company_id},
        )

    return {"user_id": user_id, "removed": True}


# ─── POST /companies/{company_id}/members/leave-request ──────────────────────

@router.post("/{company_id}/members/leave-request", status_code=202)
async def request_leave(
    company_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "viewer" or current_user.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail="Only viewers of this company can request leave")

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET leave_request_status = 'PENDING', updated_at = NOW() WHERE id = $1",
            current_user["id"],
        )

    return {"message": "Leave request submitted. Awaiting manager approval."}


# ─── POST /companies/{company_id}/members/leave-approve/{user_id} ────────────

class LeaveApproveRequest(BaseModel):
    action: str  # "approve" | "reject"


@router.post("/{company_id}/members/leave-approve/{user_id}", status_code=200)
async def approve_leave(
    company_id: int,
    user_id: int,
    body: LeaveApproveRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager(current_user, company_id)

    if body.action not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="action must be 'approve' or 'reject'")

    async with pool.acquire() as conn:
        target = await conn.fetchrow(
            """
            SELECT id, leave_request_status
            FROM users
            WHERE id = $1 AND company_id = $2 AND role = 'viewer'
            """,
            user_id, company_id,
        )
        if not target:
            raise HTTPException(status_code=404, detail="Viewer with pending leave not found")
        if target["leave_request_status"] != "PENDING":
            raise HTTPException(status_code=400, detail="No pending leave request for this user")

        if body.action == "approve":
            await conn.execute(
                """
                UPDATE users
                SET company_id = NULL, role = NULL, leave_request_status = 'APPROVED',
                    updated_at = NOW()
                WHERE id = $1
                """,
                user_id,
            )
            await log_admin_action(
                conn, current_user["id"], "approve_leave", "user", user_id,
                {"company_id": company_id},
            )
        else:
            await conn.execute(
                "UPDATE users SET leave_request_status = 'REJECTED', updated_at = NOW() WHERE id = $1",
                user_id,
            )

    return {"user_id": user_id, "action": body.action}


# ─── PATCH /companies/{company_id} ────────────────────────────────────────────
# TASK-002: update company_settings.company_name

class UpdateCompanyRequest(BaseModel):
    company_name: str | None = None
    show_name_in_header: bool | None = None
    show_logo_in_header: bool | None = None


@router.patch("/{company_id}")
async def update_company(
    company_id: int,
    body: UpdateCompanyRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager_or_super_admin(current_user, company_id)

    if body.company_name is None and body.show_name_in_header is None and body.show_logo_in_header is None:
        raise HTTPException(status_code=422, detail="No fields to update")

    async with pool.acquire() as conn:
        company = await conn.fetchrow("SELECT id FROM companies WHERE id = $1", company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        updates = []
        values: list = []
        idx = 1
        meta: dict = {}
        if body.company_name is not None:
            updates.append(f"company_name = ${idx}")
            values.append(body.company_name.strip())
            meta["company_name"] = body.company_name.strip()
            idx += 1
        if body.show_name_in_header is not None:
            updates.append(f"show_name_in_header = ${idx}")
            values.append(body.show_name_in_header)
            idx += 1
        if body.show_logo_in_header is not None:
            updates.append(f"show_logo_in_header = ${idx}")
            values.append(body.show_logo_in_header)
            idx += 1

        values.append(company_id)
        await conn.execute(
            f"""
            INSERT INTO company_settings (company_id, updated_at)
            VALUES (${idx}, NOW())
            ON CONFLICT (company_id) DO UPDATE
                SET {', '.join(updates)}, updated_at = NOW()
            """,
            *values,
        )
        if meta:
            await log_admin_action(
                conn, current_user["id"], "update_company", "company", company_id, meta,
            )

    return {"updated": True}


# ─── GET/PATCH /companies/{company_id}/settings ───────────────────────────────
# TC-019/TC-020 + AC-016: timezone + notification toggles

class UpdateSettingsRequest(BaseModel):
    timezone: str | None = None
    notify_pipeline_failure: bool | None = None
    notify_pipeline_success: bool | None = None


@router.get("/{company_id}/settings")
async def get_company_settings(
    company_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager_or_super_admin(current_user, company_id)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT timezone, notify_pipeline_failure, notify_pipeline_success
            FROM company_settings
            WHERE company_id = $1
            """,
            company_id,
        )

    if not row:
        return {"timezone": "Asia/Jakarta", "notify_pipeline_failure": True, "notify_pipeline_success": False}
    return dict(row)


@router.patch("/{company_id}/settings")
async def update_company_settings(
    company_id: int,
    body: UpdateSettingsRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager_or_super_admin(current_user, company_id)

    async with pool.acquire() as conn:
        company = await conn.fetchrow("SELECT id FROM companies WHERE id = $1", company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        updates = []
        values: list = []
        idx = 1
        if body.timezone is not None:
            updates.append(f"timezone = ${idx}")
            values.append(body.timezone)
            idx += 1
        if body.notify_pipeline_failure is not None:
            updates.append(f"notify_pipeline_failure = ${idx}")
            values.append(body.notify_pipeline_failure)
            idx += 1
        if body.notify_pipeline_success is not None:
            updates.append(f"notify_pipeline_success = ${idx}")
            values.append(body.notify_pipeline_success)
            idx += 1

        if not updates:
            raise HTTPException(status_code=422, detail="No fields to update")

        values.append(company_id)
        await conn.execute(
            f"""
            UPDATE company_settings
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE company_id = ${idx}
            """,
            *values,
        )

    return {"updated": True}


# ─── POST /companies/{company_id}/logo ────────────────────────────────────────
# TASK-003: logo upload (manager only)

def _logo_dir(company_id: int) -> Path:
    d = UPLOADS_BASE / "logos" / str(company_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resize_logo(file_bytes: bytes, ext: str) -> bytes:
    if ext == ".svg":
        return file_bytes
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if img.mode == "P" else "RGB")
    w, h = img.size
    scale = min(LOGO_MAX_WIDTH / w, LOGO_MAX_HEIGHT / h, 1.0)
    if scale < 1.0:
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    out = io.BytesIO()
    fmt = "PNG" if ext in (".png", ".svg") else "JPEG"
    img.save(out, format=fmt)
    return out.getvalue()


@router.post("/{company_id}/logo")
async def upload_logo(
    company_id: int,
    file: UploadFile = File(...),
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager(current_user, company_id)

    content_type = file.content_type or ""
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    if content_type not in ALLOWED_LOGO_TYPES and ext not in ALLOWED_LOGO_EXTENSIONS:
        raise HTTPException(status_code=422, detail="Only PNG, JPEG, and SVG files are accepted")

    file_bytes = await file.read(LOGO_MAX_BYTES + 1)
    if len(file_bytes) > LOGO_MAX_BYTES:
        raise HTTPException(status_code=422, detail="Logo must be 2 MB or smaller")

    if ext not in ALLOWED_LOGO_EXTENSIONS:
        ext = ".png" if "png" in content_type else (".svg" if "svg" in content_type else ".jpg")

    resized = _resize_logo(file_bytes, ext)

    logo_dir = _logo_dir(company_id)
    save_ext = ext if ext != ".jpeg" else ".jpg"
    logo_path = logo_dir / f"logo{save_ext}"

    logo_path.write_bytes(resized)

    rel_path = str(logo_path.relative_to(UPLOADS_BASE.parent))

    async with pool.acquire() as conn:
        company = await conn.fetchrow("SELECT id FROM companies WHERE id = $1", company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        await conn.execute(
            """
            INSERT INTO company_settings (company_id, logo_path, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (company_id) DO UPDATE
                SET logo_path = EXCLUDED.logo_path, updated_at = NOW()
            """,
            company_id, rel_path,
        )

    return {"logo_path": rel_path}


# ─── DELETE /companies/{company_id}/logo ──────────────────────────────────────

@router.delete("/{company_id}/logo")
async def delete_logo(
    company_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager(current_user, company_id)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT logo_path FROM company_settings WHERE company_id = $1", company_id
        )
        if not row or not row["logo_path"]:
            raise HTTPException(status_code=404, detail="No logo to delete")

        logo_file = UPLOADS_BASE.parent / row["logo_path"]
        if logo_file.exists():
            logo_file.unlink()

        await conn.execute(
            "UPDATE company_settings SET logo_path = NULL, updated_at = NOW() WHERE company_id = $1",
            company_id,
        )

    return {"deleted": True}


# ─── GET /companies/{company_id}/logo ─────────────────────────────────────────
# TASK-004: serve logo file

@router.get("/{company_id}/logo")
async def get_logo(
    company_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT logo_path FROM company_settings WHERE company_id = $1", company_id
        )

    if not row or not row["logo_path"]:
        raise HTTPException(status_code=404, detail="No logo set for this company")

    logo_file = UPLOADS_BASE.parent / row["logo_path"]
    if not logo_file.exists():
        raise HTTPException(status_code=404, detail="Logo file not found")

    ext = logo_file.suffix.lower()
    media_type = (
        "image/svg+xml" if ext == ".svg"
        else "image/png" if ext == ".png"
        else "image/jpeg"
    )
    return FileResponse(str(logo_file), media_type=media_type)


# ─── GET /companies/{company_id}/branding ─────────────────────────────────────
# Returns branding settings for Layout header rendering

@router.get("/{company_id}/branding")
async def get_branding(
    company_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT cs.company_name, cs.show_name_in_header, cs.show_logo_in_header,
                   cs.logo_path, c.company_name AS canonical_name
            FROM company_settings cs
            JOIN companies c ON c.id = cs.company_id
            WHERE cs.company_id = $1
            """,
            company_id,
        )

    if not row:
        return {"company_name": None, "show_name_in_header": False, "show_logo_in_header": False, "has_logo": False}

    display_name = row["company_name"] or row["canonical_name"]
    return {
        "company_name": display_name,
        "show_name_in_header": row["show_name_in_header"],
        "show_logo_in_header": row["show_logo_in_header"],
        "has_logo": bool(row["logo_path"]),
    }


# ─── GET /companies/{company_id}/estate-change/status ────────────────────────

@router.get("/{company_id}/estate-change/status")
async def get_estate_change_status(
    company_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager_or_super_admin(current_user, company_id)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT estate_change_status, estate_change_reject_reason, estate_change_requested_at
            FROM company_settings WHERE company_id = $1
            """,
            company_id,
        )

    if not row:
        return {"estate_change_status": "NONE", "estate_change_reject_reason": None,
                "estate_change_requested_at": None}
    return dict(row)


# ─── POST /companies/{company_id}/estate-change/request ──────────────────────
# TASK-005: manager submits estate change file

@router.post("/{company_id}/estate-change/request", status_code=202)
async def request_estate_change(
    company_id: int,
    file: UploadFile = File(...),
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager(current_user, company_id)

    async with pool.acquire() as conn:
        cs = await conn.fetchrow(
            "SELECT estate_change_status FROM company_settings WHERE company_id = $1",
            company_id,
        )

    if cs and cs["estate_change_status"] == "PENDING":
        raise HTTPException(status_code=409, detail="An estate change request is already pending")

    file_bytes = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1)
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds maximum upload size ({settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB)",
        )

    filename = file.filename or "upload.geojson"
    conversion_warnings: list[str] = []
    lower_name = filename.lower()
    if lower_name.endswith(".zip") or lower_name.endswith(".kml") or lower_name.endswith(".kmz"):
        try:
            file_bytes, conversion_warnings = convert_to_geojson_bytes(file_bytes, filename)
            filename = filename.rsplit(".", 1)[0] + ".geojson"
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    result = validate_geojson_bytes(file_bytes, filename)
    if result.file_error:
        raise HTTPException(status_code=422, detail=result.file_error)

    ec_dir = UPLOADS_BASE / "estate_changes" / str(company_id)
    ec_dir.mkdir(parents=True, exist_ok=True)
    save_path = ec_dir / "request.geojson"
    save_path.write_bytes(file_bytes)

    rel_path = str(save_path.relative_to(UPLOADS_BASE.parent))

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO company_settings (company_id, estate_change_status, estate_change_requested_at,
                                          estate_change_file_path, estate_change_reject_reason, updated_at)
            VALUES ($1, 'PENDING', NOW(), $2, NULL, NOW())
            ON CONFLICT (company_id) DO UPDATE
                SET estate_change_status = 'PENDING',
                    estate_change_requested_at = NOW(),
                    estate_change_file_path = EXCLUDED.estate_change_file_path,
                    estate_change_reject_reason = NULL,
                    updated_at = NOW()
            """,
            company_id, rel_path,
        )
        await log_admin_action(
            conn, current_user["id"], "estate_change_request", "company", company_id,
            {"file": rel_path, "warnings": conversion_warnings},
        )

    return {"status": "PENDING", "warnings": conversion_warnings}


# ─── POST /companies/{company_id}/estate-change/cancel ────────────────────────
# TASK-006

@router.post("/{company_id}/estate-change/cancel")
async def cancel_estate_change(
    company_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _require_manager(current_user, company_id)

    async with pool.acquire() as conn:
        cs = await conn.fetchrow(
            "SELECT estate_change_status, estate_change_file_path FROM company_settings WHERE company_id = $1",
            company_id,
        )

    if not cs or cs["estate_change_status"] != "PENDING":
        raise HTTPException(status_code=400, detail="No pending estate change request to cancel")

    if cs["estate_change_file_path"]:
        ec_file = UPLOADS_BASE.parent / cs["estate_change_file_path"]
        if ec_file.exists():
            ec_file.unlink()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE company_settings
            SET estate_change_status = 'NONE', estate_change_file_path = NULL,
                estate_change_requested_at = NULL, updated_at = NOW()
            WHERE company_id = $1
            """,
            company_id,
        )

    return {"status": "NONE", "cancelled": True}
