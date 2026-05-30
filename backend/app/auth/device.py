import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import asyncpg

from app.database import settings

# Pre-computed bcrypt hash for constant-time dummy OTP comparison.
# Prevents timing side-channel when session not found or already used.
_DUMMY_OTP_HASH = "$2b$12$eMBQyN5jWpkJXL6pSv9pqecvgvZGK/ALzVFTyHIgpyLhXQRXSEWUW"


def generate_device_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_device_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def is_known_device(
    conn: asyncpg.Connection, user_id: int, raw_token: str | None
) -> bool:
    if not raw_token:
        return False
    device_hash = _hash_device_token(raw_token)
    row = await conn.fetchrow(
        """
        SELECT id FROM canopysense.known_devices
        WHERE user_id = $1 AND device_hash = $2 AND expires_at > NOW()
        """,
        user_id,
        device_hash,
    )
    if row:
        await conn.execute(
            "UPDATE canopysense.known_devices SET last_seen_at = NOW() WHERE id = $1",
            row["id"],
        )
        return True
    return False


async def register_device(
    conn: asyncpg.Connection,
    user_id: int,
    raw_token: str,
    label: str | None = None,
) -> None:
    device_hash = _hash_device_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.DEVICE_TOKEN_EXPIRE_DAYS)
    await conn.execute(
        """
        INSERT INTO canopysense.known_devices (user_id, device_hash, device_label, expires_at)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (device_hash) DO UPDATE SET last_seen_at = NOW(), expires_at = $4
        """,
        user_id,
        device_hash,
        label,
        expires_at,
    )


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def create_otp_session(
    conn: asyncpg.Connection,
    user_id: int,
    otp_code: str,
) -> int:
    from app.auth.jwt import get_password_hash

    otp_hash = get_password_hash(otp_code)
    otp_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    row = await conn.fetchrow(
        """
        INSERT INTO canopysense.device_otp_sessions (user_id, otp_hash, otp_expires_at)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        user_id,
        otp_hash,
        otp_expires,
    )
    return row["id"]


async def verify_otp_session(
    conn: asyncpg.Connection,
    session_id: int,
    otp_code: str,
) -> dict | None:
    from app.auth.jwt import verify_password

    row = await conn.fetchrow(
        """
        SELECT id, user_id, otp_hash, otp_expires_at, used
        FROM canopysense.device_otp_sessions
        WHERE id = $1
        """,
        session_id,
    )
    if not row or row["used"] or row["otp_expires_at"] < datetime.now(timezone.utc):
        # Constant-time: always run a bcrypt comparison to prevent timing side-channel
        verify_password(otp_code, _DUMMY_OTP_HASH)
        return None

    if not verify_password(otp_code, row["otp_hash"]):
        return None

    await conn.execute(
        "UPDATE canopysense.device_otp_sessions SET used = TRUE WHERE id = $1",
        session_id,
    )
    return dict(row)


async def check_resend_limit(conn: asyncpg.Connection, user_id: int) -> bool:
    """Return True if user has sent fewer than 3 OTPs in the last 10 minutes."""
    count = await conn.fetchval(
        """
        SELECT COUNT(*) FROM canopysense.device_otp_sessions
        WHERE user_id = $1 AND created_at > NOW() - INTERVAL '10 minutes'
        """,
        user_id,
    )
    return count < 3
