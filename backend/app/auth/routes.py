from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.jwt import verify_password, create_access_token
from app.api.deps import get_current_user
from app.database import get_db_pool, settings
from datetime import timedelta
import asyncpg
from pydantic import BaseModel

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class UserContext(BaseModel):
    username: str
    role: str | None
    company_id: int | None
    subscription_tier: str | None

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """SELECT u.id, u.username, u.password_hash, u.company_id, r.role
               FROM users u
               LEFT JOIN user_company_roles r ON u.id = r.user_id AND u.company_id = r.company_id
               WHERE u.username = $1""",
            form_data.username
        )

    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
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
async def get_me(
    current_user: dict = Depends(get_current_user),
):
    return {
        "username": current_user["username"],
        "role": current_user["role"],
        "company_id": current_user["company_id"],
        "subscription_tier": current_user.get("subscription_tier"),
    }
