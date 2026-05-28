from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.jwt import verify_password, create_access_token, get_password_hash
from app.api.deps import get_current_user
from app.database import get_db_pool, settings
from datetime import timedelta, datetime
import asyncpg
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class UserContext(BaseModel):
    username: str
    role: Optional[str]
    company_id: Optional[int]
    subscription_tier: Optional[str]
    is_admin: bool
    is_global_admin: bool


class SetupRequest(BaseModel):
    token: str
    new_password: str
    full_name: str
    username: str


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """SELECT u.id, u.username, u.password_hash, u.company_id, u.is_active, u.setup_required, r.role
               FROM users u
               LEFT JOIN user_company_roles r ON u.id = r.user_id AND u.company_id = r.company_id
               WHERE u.username = $1""",
            form_data.username,
        )

    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    if user["setup_required"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account setup required. Use the setup link provided by your admin.",
        )

    expires_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "user_id": user["id"],
            "company_id": user["company_id"],
            "role": user["role"],
        },
        expires_delta=access_token_expires,
    )

    return {"access_token": access_token, "token_type": "bearer", "expires_in": expires_seconds}


@router.get("/me", response_model=UserContext)
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "username": current_user["username"],
        "role": current_user.get("role"),
        "company_id": current_user.get("company_id"),
        "subscription_tier": current_user.get("subscription_tier"),
        "is_admin": bool(current_user.get("is_admin", False)),
        "is_global_admin": bool(current_user.get("is_global_admin", False)),
    }


@router.post("/setup", status_code=200)
async def setup_account(
    body: SetupRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """First-login account setup for Manager users invited by an admin."""
    async with pool.acquire() as conn:
        # Find user by matching any user with setup_required=TRUE
        # We look up by token match (no username known yet to caller)
        candidates = await conn.fetch(
            """
            SELECT id, setup_token_hash, setup_token_expires_at, setup_required
            FROM users
            WHERE setup_required = TRUE
              AND setup_token_hash IS NOT NULL
              AND setup_token_expires_at > NOW()
            """
        )

        matched_user_id = None
        for candidate in candidates:
            if verify_password(body.token, candidate["setup_token_hash"]):
                matched_user_id = candidate["id"]
                break

        if matched_user_id is None:
            raise HTTPException(status_code=400, detail="Invalid or expired setup token")

        # Ensure new username is not already taken (by a different user)
        taken = await conn.fetchval(
            "SELECT id FROM users WHERE username = $1 AND id != $2",
            body.username, matched_user_id,
        )
        if taken:
            raise HTTPException(status_code=409, detail="Username already in use")

        await conn.execute(
            """
            UPDATE users
            SET username = $1,
                full_name = $2,
                password_hash = $3,
                setup_required = FALSE,
                setup_token_hash = NULL,
                setup_token_expires_at = NULL,
                updated_at = NOW()
            WHERE id = $4
            """,
            body.username,
            body.full_name,
            get_password_hash(body.new_password),
            matched_user_id,
        )

    return {"message": "Account setup complete. You can now log in with your new credentials."}
