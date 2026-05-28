from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_admin
from app.api.admin.audit_log import log_admin_action
from app.database import get_db_pool
import asyncpg
from pydantic import BaseModel
from typing import Optional
import uuid

router = APIRouter()


class CompanyCreate(BaseModel):
    company_name: str
    metadata: Optional[dict] = None


class CompanyOut(BaseModel):
    id: int
    company_id: str
    company_name: str
    created_at: str


@router.get("")
async def list_companies(
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    admin=Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        if search:
            rows = await conn.fetch(
                """
                SELECT id, company_id, company_name, created_at
                FROM companies
                WHERE company_name ILIKE $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                f"%{search}%", limit, offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM companies WHERE company_name ILIKE $1",
                f"%{search}%",
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, company_id, company_name, created_at
                FROM companies
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM companies")
    return {
        "total": total,
        "items": [dict(r) for r in rows],
    }


@router.post("", status_code=201)
async def create_company(
    body: CompanyCreate,
    admin=Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    import json
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT id FROM companies WHERE company_name = $1", body.company_name
        )
        if existing:
            raise HTTPException(status_code=409, detail="Company name already exists")

        company_uuid = str(uuid.uuid4())
        metadata_json = json.dumps(body.metadata or {})
        row = await conn.fetchrow(
            """
            INSERT INTO companies (company_id, company_name, metadata)
            VALUES ($1, $2, $3)
            RETURNING id, company_id, company_name, created_at
            """,
            company_uuid, body.company_name, metadata_json,
        )
        # Seed an empty subscription (basic) so readiness checks work
        await conn.execute(
            """
            INSERT INTO company_subscriptions (company_id, tier, status)
            VALUES ($1, 'basic', 'active')
            ON CONFLICT (company_id) DO NOTHING
            """,
            row["id"],
        )
        await log_admin_action(conn, admin["id"], "create_company", "company", row["id"],
                               {"company_name": body.company_name})
    return dict(row)


@router.get("/{company_id}")
async def get_company_detail(
    company_id: int,
    admin=Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        company = await conn.fetchrow(
            "SELECT id, company_id, company_name, created_at, metadata FROM companies WHERE id = $1",
            company_id,
        )
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        # Operational readiness counts
        estate_count = await conn.fetchval(
            "SELECT COUNT(*) FROM canopysense.estates WHERE company_id = $1", company_id
        )
        block_count = await conn.fetchval(
            "SELECT COUNT(*) FROM canopysense.blocks WHERE company_id = $1", company_id
        )
        satellite_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM canopysense.satellite_data sd
            JOIN canopysense.blocks b ON sd.block_id = b.id
            WHERE b.company_id = $1
            """,
            company_id,
        )
        subscription = await conn.fetchrow(
            """
            SELECT tier, status, billing_interval, subscription_starts_at,
                   subscription_ends_at, timelapse_enabled, timelapse_period_months, raster_serving_mode
            FROM company_subscriptions WHERE company_id = $1
            """,
            company_id,
        )
        managers = await conn.fetch(
            """
            SELECT u.id, u.username, u.full_name, u.email, u.is_active, u.setup_required
            FROM users u
            JOIN user_company_roles ucr ON u.id = ucr.user_id AND u.company_id = $1
            WHERE ucr.role = 'manager'
            ORDER BY u.created_at DESC
            """,
            company_id,
        )
    return {
        "company": dict(company),
        "readiness": {
            "estates": estate_count,
            "blocks": block_count,
            "satellite_records": satellite_count,
            "has_subscription": subscription is not None,
        },
        "subscription": dict(subscription) if subscription else None,
        "managers": [dict(m) for m in managers],
    }
