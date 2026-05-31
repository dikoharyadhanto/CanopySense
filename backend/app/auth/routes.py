import re
import secrets
from datetime import datetime, timedelta
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
from app.services.email import (
    send_otp_email,
    send_password_reset_email,
    send_viewer_invite_email,
)

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


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ProfilePatchRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AcceptViewerInviteRequest(BaseModel):
    token: str


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
            SELECT id, username, password_hash, company_id, is_active,
                   setup_required, email, is_admin, is_global_admin, role
            FROM users
            WHERE username = $1
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
            "SELECT id, username, company_id, is_active, role FROM users WHERE id = $1",
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
        secure=settings.ENVIRONMENT == "production",
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


# ─── POST /forgot-password ────────────────────────────────────────────────────

@router.post("/forgot-password", status_code=200)
@limiter.limit("5/hour")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Always returns 200 — anti-enumeration (AC-001, TC-001)."""
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, username, email FROM users WHERE email = $1 AND is_active = TRUE",
            body.email,
        )

    if user:
        plaintext = secrets.token_urlsafe(32)
        token_hash = get_password_hash(plaintext)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET password_reset_token_hash = $1,
                    password_reset_token_expires_at = $2,
                    updated_at = NOW()
                WHERE id = $3
                """,
                token_hash, expires_at, user["id"],
            )

        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={plaintext}"
        try:
            await send_password_reset_email(user["email"], user["username"], reset_link)
        except Exception:
            pass

    return {"message": "If that email is registered, a reset link has been sent."}


# ─── POST /reset-password ─────────────────────────────────────────────────────

@router.post("/reset-password", status_code=200)
@limiter.limit("10/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    _enforce_password_policy(body.new_password)

    async with pool.acquire() as conn:
        candidates = await conn.fetch(
            """
            SELECT id, password_reset_token_hash
            FROM users
            WHERE password_reset_token_hash IS NOT NULL
              AND password_reset_token_expires_at > NOW()
            """
        )

        matched_id = None
        for c in candidates:
            if verify_password(body.token, c["password_reset_token_hash"]):
                matched_id = c["id"]
                break

        if matched_id is None:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        await conn.execute(
            """
            UPDATE users
            SET password_hash = $1,
                password_reset_token_hash = NULL,
                password_reset_token_expires_at = NULL,
                updated_at = NOW()
            WHERE id = $2
            """,
            get_password_hash(body.new_password),
            matched_id,
        )

    return {"message": "Password reset successful. You can now log in with your new password."}


# ─── GET /profile ─────────────────────────────────────────────────────────────

@router.get("/profile")
async def get_profile(
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.username, u.full_name, u.email, u.role, u.company_id,
                   c.company_name
            FROM users u
            LEFT JOIN companies c ON c.id = u.company_id
            WHERE u.id = $1
            """,
            current_user["id"],
        )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


# ─── PATCH /profile ───────────────────────────────────────────────────────────

@router.patch("/profile")
async def update_profile(
    body: ProfilePatchRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]

    async with pool.acquire() as conn:
        if body.email is not None:
            conflict = await conn.fetchval(
                "SELECT id FROM users WHERE email = $1 AND id != $2", body.email, user_id
            )
            if conflict:
                raise HTTPException(status_code=400, detail="Email already in use")

        if body.username is not None:
            conflict = await conn.fetchval(
                "SELECT id FROM users WHERE username = $1 AND id != $2", body.username, user_id
            )
            if conflict:
                raise HTTPException(status_code=400, detail="Username already in use")

        sets, params = [], [user_id]
        idx = 2
        if body.full_name is not None:
            sets.append(f"full_name = ${idx}"); params.append(body.full_name); idx += 1
        if body.email is not None:
            sets.append(f"email = ${idx}"); params.append(body.email); idx += 1
        if body.username is not None:
            sets.append(f"username = ${idx}"); params.append(body.username); idx += 1

        if sets:
            sets.append("updated_at = NOW()")
            await conn.execute(
                f"UPDATE users SET {', '.join(sets)} WHERE id = $1", *params
            )

        row = await conn.fetchrow(
            "SELECT id, username, full_name, email, role, company_id FROM users WHERE id = $1",
            user_id,
        )
    return dict(row)


# ─── POST /change-password ────────────────────────────────────────────────────

@router.post("/change-password", status_code=200)
async def change_password(
    body: ChangePasswordRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(get_current_user),
):
    _enforce_password_policy(body.new_password)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT password_hash FROM users WHERE id = $1", current_user["id"]
        )
        if not row or not verify_password(body.current_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        await conn.execute(
            "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2",
            get_password_hash(body.new_password), current_user["id"],
        )

    return {"message": "Password changed successfully."}


# ─── POST /accept-viewer-invite ───────────────────────────────────────────────

@router.post("/accept-viewer-invite", status_code=200)
@limiter.limit("10/minute")
async def accept_viewer_invite(
    request: Request,
    body: AcceptViewerInviteRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        candidates = await conn.fetch(
            """
            SELECT id, viewer_invite_token_hash, company_id
            FROM users
            WHERE viewer_invite_token_hash IS NOT NULL
              AND viewer_invite_token_expires_at > NOW()
            """
        )

        matched = None
        for c in candidates:
            if verify_password(body.token, c["viewer_invite_token_hash"]):
                matched = c
                break

        if matched is None:
            raise HTTPException(status_code=400, detail="Invalid or expired invitation token")

        user_row = await conn.fetchrow(
            "SELECT setup_required FROM users WHERE id = $1", matched["id"]
        )
        needs_setup = user_row["setup_required"] if user_row else False

        setup_token_plaintext = None
        if needs_setup:
            setup_token_plaintext = secrets.token_urlsafe(32)
            setup_token_hash = get_password_hash(setup_token_plaintext)
            setup_token_expires = datetime.utcnow() + timedelta(hours=24)
            await conn.execute(
                """
                UPDATE users
                SET role = 'viewer',
                    company_id = $1,
                    viewer_invite_token_hash = NULL,
                    viewer_invite_token_expires_at = NULL,
                    setup_token_hash = $2,
                    setup_token_expires_at = $3,
                    updated_at = NOW()
                WHERE id = $4
                """,
                matched["company_id"], setup_token_hash, setup_token_expires, matched["id"],
            )
        else:
            await conn.execute(
                """
                UPDATE users
                SET role = 'viewer',
                    company_id = $1,
                    viewer_invite_token_hash = NULL,
                    viewer_invite_token_expires_at = NULL,
                    updated_at = NOW()
                WHERE id = $2
                """,
                matched["company_id"], matched["id"],
            )

        company = await conn.fetchrow(
            "SELECT company_name FROM companies WHERE id = $1", matched["company_id"]
        )

    company_name = company["company_name"] if company else None
    if needs_setup:
        return {
            "message": "Invitation accepted. Please complete your account setup.",
            "company_name": company_name,
            "needs_setup": True,
            "setup_token": setup_token_plaintext,
        }
    return {"message": "Invitation accepted.", "company_name": company_name, "needs_setup": False}
