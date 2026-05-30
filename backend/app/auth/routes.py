import re
from datetime import timedelta
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.auth.device import (
    check_resend_limit,
    create_otp_session,
    generate_device_token,
    generate_otp,
    is_known_device,
    register_device,
    verify_otp_session,
)
from app.auth.jwt import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.database import get_db_pool, settings
from app.limiter import limiter
from app.services.email import send_otp_email

router = APIRouter()

# Pre-computed bcrypt hash used for constant-time comparison when the username is
# not found — prevents username enumeration via login timing side-channel.
_DUMMY_HASH = "$2b$12$eMBQyN5jWpkJXL6pSv9pqecvgvZGK/ALzVFTyHIgpyLhXQRXSEWUW"

# Password policy: ≥12 chars, at least one uppercase, one lowercase, one digit or special char
_PASSWORD_RE = re.compile(
    r'^(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9!@#$%^&*()\-_=+\[\]{};:\'",.<>/?\\|`~]).{12,}$'
)


def _enforce_password_policy(password: str) -> None:
    if not _PASSWORD_RE.match(password):
        raise HTTPException(
            status_code=422,
            detail="Password does not meet requirements",
        )


# ─── Pydantic models ──────────────────────────────────────────────────────────

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


class VerifyDeviceRequest(BaseModel):
    pending_token: str
    otp_code: str


class ResendOTPRequest(BaseModel):
    pending_token: str


# ─── POST /login ──────────────────────────────────────────────────────────────

@router.post("/login")
@limiter.limit("10/minute")
async def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT u.id, u.username, u.password_hash, u.company_id, u.is_active,
                   u.setup_required, u.email, u.is_admin, u.is_global_admin, r.role
            FROM users u
            LEFT JOIN user_company_roles r ON u.id = r.user_id AND u.company_id = r.company_id
            WHERE u.username = $1
            """,
            form_data.username,
        )

    # Constant-time: always run bcrypt to prevent username enumeration via timing (TC-008)
    if not user:
        verify_password(form_data.password, _DUMMY_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user["password_hash"]):
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

    is_privileged = bool(user["is_admin"]) or bool(user["is_global_admin"])

    if is_privileged:
        # Device challenge for admin and super-admin (Phase E)
        device_token_raw = (
            request.cookies.get("device_token")
            or request.headers.get("X-Device-Token")
        )

        async with pool.acquire() as conn:
            known = await is_known_device(conn, user["id"], device_token_raw)

        if not known:
            # Unknown device: issue OTP, return 202 (no access token yet)
            otp_code = generate_otp()
            async with pool.acquire() as conn:
                session_id = await create_otp_session(conn, user["id"], otp_code)

            try:
                await send_otp_email(user["email"], otp_code, user["username"])
            except Exception:
                # Email failure must not block the flow or reveal internal state
                pass

            pending_token = create_access_token(
                data={"sub": "device_otp", "session_id": session_id, "user_id": user["id"]},
                expires_delta=timedelta(minutes=5),
            )
            return JSONResponse(
                status_code=202,
                content={
                    "pending_token": pending_token,
                    "message": "A verification code has been sent to your registered email address.",
                },
            )

    # Known device or non-privileged role (manager) — issue access token
    expires_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "user_id": user["id"],
            "company_id": user["company_id"],
            "role": user["role"],
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer", "expires_in": expires_seconds}


# ─── POST /verify-device ──────────────────────────────────────────────────────

@router.post("/verify-device")
@limiter.limit("10/minute")
async def verify_device(
    request: Request,
    response: Response,
    body: VerifyDeviceRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Verify OTP from email. On success: issue access token + set device_token cookie."""
    payload = decode_access_token(body.pending_token)
    if not payload or payload.get("sub") != "device_otp":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired verification token",
        )

    session_id = payload.get("session_id")
    user_id = payload.get("user_id")
    if not session_id or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired verification token",
        )

    async with pool.acquire() as conn:
        session = await verify_otp_session(conn, session_id, body.otp_code)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP",
            )

        user = await conn.fetchrow(
            """
            SELECT u.id, u.username, u.company_id, u.is_active, r.role
            FROM users u
            LEFT JOIN user_company_roles r ON u.id = r.user_id AND u.company_id = r.company_id
            WHERE u.id = $1
            """,
            user_id,
        )
        if not user or not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        raw_device_token = generate_device_token()
        await register_device(conn, user_id, raw_device_token)

    response.set_cookie(
        key="device_token",
        value=raw_device_token,
        max_age=settings.DEVICE_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=True,
        samesite="strict",
    )

    expires_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "user_id": user["id"],
            "company_id": user["company_id"],
            "role": user["role"],
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer", "expires_in": expires_seconds}


# ─── POST /resend-otp ─────────────────────────────────────────────────────────

@router.post("/resend-otp")
@limiter.limit("5/minute")
async def resend_otp(
    request: Request,
    body: ResendOTPRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Resend OTP to the user's email. Rate-limited to 3 resends per 10 minutes per user."""
    payload = decode_access_token(body.pending_token)
    if not payload or payload.get("sub") != "device_otp":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired verification token",
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired verification token",
        )

    async with pool.acquire() as conn:
        can_resend = await check_resend_limit(conn, user_id)
        if not can_resend:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests. Please wait before requesting a new code.",
            )

        user = await conn.fetchrow(
            "SELECT id, username, email FROM users WHERE id = $1", user_id
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        otp_code = generate_otp()
        session_id = await create_otp_session(conn, user_id, otp_code)

    try:
        await send_otp_email(user["email"], otp_code, user["username"])
    except Exception:
        pass

    pending_token = create_access_token(
        data={"sub": "device_otp", "session_id": session_id, "user_id": user_id},
        expires_delta=timedelta(minutes=5),
    )
    return {
        "pending_token": pending_token,
        "message": "A new verification code has been sent to your email.",
    }


# ─── GET /me ──────────────────────────────────────────────────────────────────

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


# ─── POST /setup ──────────────────────────────────────────────────────────────

@router.post("/setup", status_code=200)
@limiter.limit("5/minute")
async def setup_account(
    request: Request,
    body: SetupRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """First-login account setup for Manager users invited by an admin."""
    _enforce_password_policy(body.new_password)

    async with pool.acquire() as conn:
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
