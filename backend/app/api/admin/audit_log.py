import json
from typing import Any, Optional
import asyncpg


async def log_admin_action(
    conn: asyncpg.Connection,
    actor_id: int,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO admin_audit_log (actor_id, action, target_type, target_id, metadata)
        VALUES ($1, $2, $3, $4, $5)
        """,
        actor_id,
        action,
        target_type,
        target_id,
        json.dumps(metadata or {}),
    )
