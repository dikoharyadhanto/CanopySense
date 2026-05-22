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
            SELECT u.id, u.username, u.company_id, u.is_active, r.role 
            FROM users u
            LEFT JOIN user_company_roles r ON u.id = r.user_id AND u.company_id = r.company_id
            WHERE u.username = $1
        """, username)
        
    if user is None:
        raise credentials_exception
    
    if not user['is_active']:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return dict(user)
