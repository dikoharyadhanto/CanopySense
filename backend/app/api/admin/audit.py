from fastapi import APIRouter, Depends
from app.api.deps import get_current_admin
from app.database import get_db_pool
import asyncpg
from typing import Optional

router = APIRouter()


@router.get("")
async def list_audit_log(
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    admin=Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        where_clauses = []
        params: list = []
        idx = 1

        # Non-super-admins see only entries they authored or company-scoped targets
        if not admin.get("is_global_admin"):
            where_clauses.append(f"al.actor_id = ${idx}")
            params.append(admin["id"])
            idx += 1

        if target_type:
            where_clauses.append(f"al.target_type = ${idx}")
            params.append(target_type)
            idx += 1

        if target_id is not None:
            where_clauses.append(f"al.target_id = ${idx}")
            params.append(target_id)
            idx += 1

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        rows = await conn.fetch(
            f"""
            SELECT al.id, al.actor_id, u.username AS actor_username,
                   al.action, al.target_type, al.target_id, al.metadata, al.created_at
            FROM admin_audit_log al
            JOIN users u ON al.actor_id = u.id
            {where_sql}
            ORDER BY al.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params, limit, offset,
        )

        count_params = params.copy()
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM admin_audit_log al {where_sql}",
            *count_params,
        )

    return {
        "total": total,
        "items": [dict(r) for r in rows],
    }
