import secrets
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_super_admin
from app.api.admin.audit_log import log_admin_action
from app.auth.jwt import get_password_hash
from app.database import get_db_pool
import asyncpg
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class AdminCreate(BaseModel):
    email: str
    full_name: str
    username: str
    password: str


class AdminStatusUpdate(BaseModel):
    is_active: bool


@router.get("")
async def list_internal_admins(
    super_admin=Depends(get_current_super_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, username, full_name, email, is_admin, is_global_admin, is_active, created_at
            FROM users
            WHERE (is_admin = TRUE OR is_global_admin = TRUE)
            ORDER BY created_at DESC
            """
        )
    return [dict(r) for r in rows]


@router.post("", status_code=201)
async def create_internal_admin(
    body: AdminCreate,
    super_admin=Depends(get_current_super_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        for field, val in [("email", body.email), ("username", body.username)]:
            conflict = await conn.fetchval(
                f"SELECT id FROM users WHERE {field} = $1", val
            )
            if conflict:
                raise HTTPException(status_code=409, detail=f"{field} already in use")

        row = await conn.fetchrow(
            """
            INSERT INTO users
                (email, full_name, username, password_hash, is_admin,
                 company_id, is_active, created_by)
            VALUES ($1, $2, $3, $4, TRUE, NULL, TRUE, $5)
            RETURNING id, username, full_name, email, is_admin, created_at
            """,
            body.email,
            body.full_name,
            body.username,
            get_password_hash(body.password),
            super_admin["id"],
        )
        await log_admin_action(conn, super_admin["id"], "create_internal_admin", "user", row["id"],
                               {"username": body.username})
    return dict(row)


@router.patch("/{user_id}/status")
async def update_internal_admin_status(
    user_id: int,
    body: AdminStatusUpdate,
    super_admin=Depends(get_current_super_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, is_global_admin FROM users WHERE id = $1 AND is_admin = TRUE",
            user_id,
        )
        if not user:
            raise HTTPException(status_code=404, detail="Internal admin not found")
        # Prevent super-admin from deactivating themselves
        if user_id == super_admin["id"]:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

        await conn.execute(
            "UPDATE users SET is_active = $1, updated_at = NOW() WHERE id = $2",
            body.is_active, user_id,
        )
        action = "reactivate_admin" if body.is_active else "deactivate_admin"
        await log_admin_action(conn, super_admin["id"], action, "user", user_id)
    return {"user_id": user_id, "is_active": body.is_active}
