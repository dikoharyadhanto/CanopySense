import asyncpg
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGUSER: str = "postgres"
    PGPASSWORD: str = "postgres"
    PGDATABASE: str = "canopysense"
    SECRET_KEY: str = "super_secret_key_change_me_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 1 week

    class Config:
        env_file = ".env"

settings = Settings()

class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            user=settings.PGUSER,
            password=settings.PGPASSWORD,
            database=settings.PGDATABASE,
            host=settings.PGHOST,
            port=settings.PGPORT,
            min_size=1,
            max_size=10,
        )

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

db = Database()

async def init_db():
    await db.connect()

async def close_db():
    await db.disconnect()

async def get_db_pool():
    return db.pool
