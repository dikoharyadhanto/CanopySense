from fastapi import APIRouter, Depends

from app.api.deps import get_current_super_admin
from app.database import settings

router = APIRouter()

_SETTINGS_ALLOWLIST = [
    "APP_VERSION",
    "CLOUD_FUNCTION_URL",
    "FRONTEND_URL",
    "ARCHIVE_RETENTION_DAYS",
    "PATCHER_API_VERSION",
    "PGSCHEMA",
    "RASTER_CACHE_TTL_SECONDS",
    "RASTER_CLOUD_TIMEOUT_SECONDS",
    "FUNCTION_TIMEOUT_SECONDS",
    "DEVICE_TOKEN_EXPIRE_DAYS",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "ENVIRONMENT",
    "ALLOWED_ORIGINS",
]


@router.get("/system-settings")
async def get_system_settings(_user: dict = Depends(get_current_super_admin)):
    result = {}
    for key in _SETTINGS_ALLOWLIST:
        value = getattr(settings, key, None)
        if value is not None:
            result[key] = str(value)
    return {"settings": result}
