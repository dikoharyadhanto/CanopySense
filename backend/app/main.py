import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth.routes import router as auth_router
from app.api.blocks import router as blocks_router
from app.api.raster import router as raster_router
from app.api.admin.router import router as admin_router
from app.database import init_db, close_db, init_redis, close_redis
from app.services.pipeline_scheduler import run_scheduler_loop

logger = logging.getLogger(__name__)

app = FastAPI(
    title="CanopySense API",
    version="1.0.0",
    description="Backend API for CanopySense Dashboard",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_scheduler_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup_event():
    global _scheduler_task
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

@app.get("/health")
async def health_check():
    return {"status": "ok"}
