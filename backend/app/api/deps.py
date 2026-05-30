from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.auth.jwt import decode_access_token
from app.database import get_db_pool
import asyncpg

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), pool: asyncpg.Pool = Depends(get_db_pool)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    async with pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT
                u.id, u.username, u.company_id, u.is_active, u.is_global_admin, u.is_admin, u.role,
                cs.tier            AS subscription_tier,
                cs.status          AS subscription_status,
                cs.timelapse_enabled,
                cs.timelapse_period_months,
                cs.raster_serving_mode
            FROM users u
            LEFT JOIN company_subscriptions cs
                   ON u.company_id = cs.company_id
            WHERE u.username = $1
        """, username)

    if user is None:
        raise credentials_exception

    if not user['is_active']:
        raise HTTPException(status_code=400, detail="Inactive user")

    return dict(user)


async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Accepts is_admin=TRUE or is_global_admin=TRUE. Re-reads DB — not JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    async with pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT id, username, company_id, is_active, is_admin, is_global_admin
            FROM users
            WHERE username = $1
        """, username)

    if user is None:
        raise credentials_exception

    if not user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")

    if not (user["is_admin"] or user["is_global_admin"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    return dict(user)


async def get_current_super_admin(
    token: str = Depends(oauth2_scheme),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Accepts only is_global_admin=TRUE. Re-reads DB — not JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    async with pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT id, username, company_id, is_active, is_admin, is_global_admin
            FROM users
            WHERE username = $1
        """, username)

    if user is None:
        raise credentials_exception

    if not user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")

    if not user["is_global_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super-admin access required")

    return dict(user)
