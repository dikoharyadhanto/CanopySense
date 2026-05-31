import asyncpg
import logging
from typing import Optional
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGUSER: str = "postgres"
    PGPASSWORD: str = ""
    PGDATABASE: str = "canopysense"
    # No default — startup validation in main.py rejects weak/empty values in non-test environments
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    # Reduced from 1 week (10080) to 60 min (GAP-06)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""
    # Raster cache TTL in seconds. Default 43200 (12h) — referenced from GEE
    # getMapId() ~48h empirical window. Configurable; not a product guarantee.
    RASTER_CACHE_TTL_SECONDS: int = 43200
    CLOUD_FUNCTION_URL: str = ""
    PATCHER_API_KEY: str = ""
    RASTER_CLOUD_TIMEOUT_SECONDS: int = 60
    CONTRACTOR_ID: str = ""
    FUNCTION_TIMEOUT_SECONDS: int = 120
    PGSCHEMA: str = "canopysense"
    PATCHER_API_VERSION: str = "1.1"
    # CORS allowlist — comma-separated origins, no wildcard (GAP-01)
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    # Email OTP settings (Phase E — new device detection)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""
    DEVICE_TOKEN_EXPIRE_DAYS: int = 90
    # Upload size limit in bytes — enforced before file.read() to prevent DoS
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    # Environment guard — set to "production" to block staging_reset.py
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    SUPERADMIN_NOTIFY_EMAIL: str = ""
    ARCHIVE_RETENTION_DAYS: int = 30
    APP_VERSION: str = "1.0.0"

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
