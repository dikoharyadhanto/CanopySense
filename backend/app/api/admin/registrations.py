import secrets
from datetime import datetime, timedelta

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.admin.audit_log import log_admin_action
from app.api.deps import get_current_super_admin
from app.auth.jwt import get_password_hash
from app.database import get_db_pool, settings

router = APIRouter()

SETUP_TOKEN_TTL_HOURS = 1


# ─── GET /admin/registrations ────────────────────────────────────────────────

@router.get("/registrations")
async def list_registrations(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    pool: asyncpg.Pool = Depends(get_db_pool),
    _user: dict = Depends(get_current_super_admin),
):
    offset = (page - 1) * page_size
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT id, company_name, contact_name, email, phone, status, reject_reason, created_at, updated_at
                FROM company_registration_requests
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                status.upper(), page_size, offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM company_registration_requests WHERE status = $1",
                status.upper(),
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, company_name, contact_name, email, phone, status, reject_reason, created_at, updated_at
                FROM company_registration_requests
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                page_size, offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM company_registration_requests")

    return {"items": [dict(r) for r in rows], "total": total, "page": page, "page_size": page_size}


# ─── POST /admin/registrations/{id}/approve ───────────────────────────────────

@router.post("/registrations/{registration_id}/approve", status_code=201)
async def approve_registration(
    registration_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
    user: dict = Depends(get_current_super_admin),
):
    async with pool.acquire() as conn:
        reg = await conn.fetchrow(
            "SELECT id, company_name, contact_name, email, status FROM company_registration_requests WHERE id = $1",
            registration_id,
        )

    if not reg:
        raise HTTPException(status_code=404, detail="Registration request not found")
    if reg["status"] != "PENDING":
        raise HTTPException(status_code=400, detail="Registration is not in PENDING state")

    plaintext_token = secrets.token_urlsafe(32)
    token_hash = get_password_hash(plaintext_token)
    expires_at = datetime.utcnow() + timedelta(hours=SETUP_TOKEN_TTL_HOURS)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Create company
            company_row = await conn.fetchrow(
                """
                INSERT INTO companies (company_id, company_name)
                VALUES (gen_random_uuid(), $1)
                RETURNING id
                """,
                reg["company_name"],
            )
            company_db_id = company_row["id"]

            # Create company_settings row
            await conn.execute(
                "INSERT INTO company_settings (company_id, updated_at) VALUES ($1, NOW())",
                company_db_id,
            )

            # Create manager user (setup_required = TRUE, temp password hash)
            provisional_username = reg["email"].split("@")[0] + "_" + secrets.token_hex(4)
            await conn.execute(
                """
                INSERT INTO users
                    (email, username, full_name, password_hash, company_id, role,
                     is_active, setup_required,
                     password_reset_token_hash, password_reset_token_expires_at)
                VALUES ($1, $2, $3, $4, $5, 'manager', TRUE, TRUE, $6, $7)
                """,
                reg["email"],
                provisional_username,
                reg["contact_name"],
                get_password_hash(secrets.token_hex(16)),
                company_db_id,
                token_hash,
                expires_at,
            )

            # Update registration status
            await conn.execute(
                "UPDATE company_registration_requests SET status = 'APPROVED', updated_at = NOW() WHERE id = $1",
                registration_id,
            )

            await log_admin_action(
                conn, user["id"], "registration_approve", "company", company_db_id,
                {"registration_id": registration_id, "email": reg["email"]},
            )

    setup_link = f"{settings.FRONTEND_URL}/setup?token={plaintext_token}"
    try:
        from app.services.email import send_registration_approval_setup_email
        await send_registration_approval_setup_email(
            reg["email"], reg["contact_name"], reg["company_name"], setup_link
        )
    except Exception:
        pass

    return {"approved": True, "company_id": company_db_id}


# ─── POST /admin/registrations/{id}/reject ───────────────────────────────────

class RejectRegistrationRequest(BaseModel):
    reason: str


@router.post("/registrations/{registration_id}/reject")
async def reject_registration(
    registration_id: int,
    body: RejectRegistrationRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
    user: dict = Depends(get_current_super_admin),
):
    async with pool.acquire() as conn:
        reg = await conn.fetchrow(
            "SELECT id, company_name, contact_name, email, status FROM company_registration_requests WHERE id = $1",
            registration_id,
        )

    if not reg:
        raise HTTPException(status_code=404, detail="Registration request not found")
    if reg["status"] != "PENDING":
        raise HTTPException(status_code=400, detail="Registration is not in PENDING state")

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE company_registration_requests
            SET status = 'REJECTED', reject_reason = $2, updated_at = NOW()
            WHERE id = $1
            """,
            registration_id, body.reason,
        )
        await log_admin_action(
            conn, user["id"], "registration_reject", "registration", registration_id,
            {"reason": body.reason, "email": reg["email"]},
        )

    try:
        from app.services.email import send_registration_rejection_email
        await send_registration_rejection_email(
            reg["email"], reg["contact_name"], reg["company_name"], body.reason
        )
    except Exception:
        pass

    return {"rejected": True}
