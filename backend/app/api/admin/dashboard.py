from fastapi import APIRouter, Depends
from app.api.deps import get_current_admin
from app.database import get_db_pool
import asyncpg

router = APIRouter()


@router.get("")
async def get_admin_dashboard(
    admin=Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        company_count = await conn.fetchval("SELECT COUNT(*) FROM companies")
        manager_count = await conn.fetchval(
            "SELECT COUNT(*) FROM users u "
            "JOIN user_company_roles ucr ON u.id = ucr.user_id "
            "WHERE ucr.role = 'manager' AND u.is_active = TRUE"
        )
        sub_stats = await conn.fetch(
            "SELECT tier, COUNT(*) AS count FROM company_subscriptions GROUP BY tier"
        )
        recent_actions = await conn.fetch(
            """
            SELECT al.id, u.username AS actor_username, al.action,
                   al.target_type, al.target_id, al.created_at
            FROM admin_audit_log al
            JOIN users u ON al.actor_id = u.id
            ORDER BY al.created_at DESC
            LIMIT 10
            """
        )
    return {
        "company_count": company_count,
        "active_manager_count": manager_count,
        "subscription_summary": {r["tier"]: r["count"] for r in sub_stats},
        "recent_audit_actions": [dict(r) for r in recent_actions],
    }
