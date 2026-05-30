import asyncio
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.auth.routes import router as auth_router
from app.api.blocks import router as blocks_router
from app.api.raster import router as raster_router
from app.api.admin.router import router as admin_router
from app.api.companies import router as companies_router
from app.database import init_db, close_db, init_redis, close_redis, settings
from app.services.pipeline_scheduler import run_scheduler_loop
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.limiter import limiter

logger = logging.getLogger(__name__)

app = FastAPI(
    title="CanopySense API",
    version="1.0.0",
    description="Backend API for CanopySense Dashboard",
)

# ─── Rate limiter ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── Security headers on every response (GAP-05) ──────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ─── Request body size limit — reject oversized requests before reading (GAP-10)
_MAX_REQUEST_SIZE = settings.MAX_UPLOAD_SIZE_BYTES


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_REQUEST_SIZE:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})
    return await call_next(request)


# ─── CORS: env-driven allowlist, no wildcard (GAP-01) ─────────────────────────
_allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_scheduler_task: asyncio.Task | None = None


def _validate_startup_config() -> None:
    """Reject weak or default SECRET_KEY in non-test environments."""
    if os.getenv("TESTING", "").lower() in ("1", "true", "yes"):
        return

    _weak = {
        "super_secret_key_change_me_in_production",
        "secret",
        "changeme",
        "password",
        "",
    }
    if settings.SECRET_KEY.lower() in _weak or len(settings.SECRET_KEY) < 32:
        raise RuntimeError(
            "Startup aborted: SECRET_KEY is weak or is the default value. "
            "Set a strong random value (≥32 chars) via the SECRET_KEY environment variable."
        )


@app.on_event("startup")
async def startup_event():
    global _scheduler_task
    _validate_startup_config()
    await init_db()
    await init_redis()
    from app.database import db
    _scheduler_task = asyncio.create_task(run_scheduler_loop(db.pool))
    logger.info("Pipeline scheduler task created")


@app.on_event("shutdown")
async def shutdown_event():
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
    await close_db()
    await close_redis()

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(blocks_router, prefix="/api", tags=["api"])
app.include_router(raster_router, prefix="/api", tags=["raster"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(companies_router, prefix="/api/companies", tags=["companies"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
