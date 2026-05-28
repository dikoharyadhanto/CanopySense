import os
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_admin
from app.api.admin.audit_log import log_admin_action
from app.auth.jwt import get_password_hash
from app.database import get_db_pool
import asyncpg
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter()

SETUP_TOKEN_TTL_HOURS = 72


class ManagerCreate(BaseModel):
    email: str
    company_id: int


class ManagerStatusUpdate(BaseModel):
    is_active: bool


@router.post("", status_code=201)
async def create_manager(
    body: ManagerCreate,
    admin=Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        company = await conn.fetchval(
            "SELECT id FROM companies WHERE id = $1", body.company_id
        )
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        existing = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1", body.email
        )
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use")

        plaintext_token = secrets.token_urlsafe(32)
        token_hash = get_password_hash(plaintext_token)
        expires_at = datetime.utcnow() + timedelta(hours=SETUP_TOKEN_TTL_HOURS)

        # Username defaults to email local part; Manager must set it at setup
        provisional_username = body.email.split("@")[0] + "_" + secrets.token_hex(4)

        user_row = await conn.fetchrow(
            """
            INSERT INTO users
                (company_id, email, full_name, username, password_hash,
                 setup_required, setup_token_hash, setup_token_expires_at,
                 is_active, created_by)
            VALUES ($1, $2, NULL, $3, $4, TRUE, $5, $6, TRUE, $7)
            RETURNING id, email, full_name, username, created_at
            """,
            body.company_id,
            body.email,
            provisional_username,
            get_password_hash(secrets.token_hex(16)),  # unusable until setup
            token_hash,
            expires_at,
            admin["id"],
        )
        await conn.execute(
            """
            INSERT INTO user_company_roles (user_id, company_id, role, promoted_by)
            VALUES ($1, $2, 'manager', $3)
            """,
            user_row["id"], body.company_id, admin["id"],
        )
        await log_admin_action(conn, admin["id"], "create_manager", "user", user_row["id"],
                               {"email": body.email, "company_id": body.company_id})
        # full_name and username are set by Manager at first-login /auth/setup

    return {
        "user": dict(user_row),
        "setup_token": plaintext_token,
        "setup_token_expires_at": expires_at.isoformat(),
        "note": "setup_token is shown only once and is not stored in plaintext.",
    }


@router.patch("/{user_id}/status")
async def update_manager_status(
    user_id: int,
    body: ManagerStatusUpdate,
    admin=Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT u.id, u.is_active, u.is_admin, u.is_global_admin
            FROM users u
            JOIN user_company_roles ucr ON u.id = ucr.user_id
            WHERE u.id = $1 AND ucr.role = 'manager'
            """,
            user_id,
        )
        if not user:
            raise HTTPException(status_code=404, detail="Manager not found")

        await conn.execute(
            "UPDATE users SET is_active = $1, updated_at = NOW() WHERE id = $2",
            body.is_active, user_id,
        )
        action = "reactivate_manager" if body.is_active else "deactivate_manager"
        await log_admin_action(conn, admin["id"], action, "user", user_id)

    return {"user_id": user_id, "is_active": body.is_active}
