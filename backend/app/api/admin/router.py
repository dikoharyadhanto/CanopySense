from fastapi import APIRouter
from app.api.admin import companies, managers, subscriptions, internal_users, audit, dashboard, pipeline

router = APIRouter()

router.include_router(dashboard.router,        prefix="/dashboard",      tags=["admin-dashboard"])
router.include_router(companies.router,        prefix="/companies",      tags=["admin-companies"])
router.include_router(managers.router,         prefix="/managers",       tags=["admin-managers"])
router.include_router(subscriptions.router,    prefix="/subscriptions",  tags=["admin-subscriptions"])
router.include_router(internal_users.router,   prefix="/internal-users", tags=["admin-internal-users"])
router.include_router(audit.router,            prefix="/audit",          tags=["admin-audit"])
router.include_router(pipeline.router,         prefix="/pipeline",       tags=["admin-pipeline"])
