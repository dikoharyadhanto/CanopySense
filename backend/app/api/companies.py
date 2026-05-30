import secrets
from datetime import datetime, timedelta

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.admin.audit_log import log_admin_action
from app.api.deps import get_current_user
from app.auth.jwt import get_password_hash, verify_password
from app.database import get_db_pool, settings
from app.limiter import limiter
from app.services.email import send_viewer_invite_email

router = APIRouter()

VIEWER_INVITE_TTL_HOURS = 48


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
