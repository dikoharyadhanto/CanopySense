from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth.routes import router as auth_router
from app.api.blocks import router as blocks_router
from app.api.raster import router as raster_router
from app.database import init_db, close_db, init_redis, close_redis

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

@app.on_event("startup")
async def startup_event():
    await init_db()
    await init_redis()

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()
    await close_redis()

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(blocks_router, prefix="/api", tags=["api"])
app.include_router(raster_router, prefix="/api", tags=["raster"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
