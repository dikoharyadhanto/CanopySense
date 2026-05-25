from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth.routes import router as auth_router
from app.api.blocks import router as blocks_router
from app.database import init_db, close_db

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

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(blocks_router, prefix="/api", tags=["api"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
