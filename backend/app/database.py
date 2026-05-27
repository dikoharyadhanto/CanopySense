import asyncpg
import logging
from typing import Optional
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGUSER: str = "postgres"
    PGPASSWORD: str = "postgres"
    PGDATABASE: str = "canopysense"
    SECRET_KEY: str = "super_secret_key_change_me_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week
    REDIS_URL: str = "redis://localhost:6379/0"
    # Raster cache TTL in seconds. Default 43200 (12h) — referenced from GEE
    # getMapId() ~48h empirical window. Configurable; not a product guarantee.
    RASTER_CACHE_TTL_SECONDS: int = 43200

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

_redis_client = None


async def init_db():
    await db.connect()


async def close_db():
    await db.disconnect()


async def get_db_pool():
    return db.pool


async def init_redis():
    global _redis_client
    try:
        import redis.asyncio as aioredis
        _redis_client = await aioredis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
        logger.info("Redis client initialized: %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning("Redis init failed (raster cache will be disabled): %s", exc)
        _redis_client = None


async def close_redis():
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception:
            pass
        _redis_client = None


async def get_redis():
    return _redis_client
