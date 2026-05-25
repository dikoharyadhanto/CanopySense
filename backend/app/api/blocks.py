from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import date
import asyncpg
import json
from app.database import get_db_pool
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/blocks")
async def get_blocks(
    estate_id: Optional[int] = None,
    afdeling_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool)
):
    query = """
        SELECT b.id as block_id, b.code, b.name,
               ST_AsGeoJSON(b.geometry)::jsonb as geometry,
               a.name as afdeling_name, e.name as estate_name,
               s.ndvi as latest_ndvi, s.evi as latest_evi,
               s.ndre as latest_ndre, s.savi as latest_savi,
               s.gndvi as latest_gndvi,
               s.acquisition_date, s.cloud_cover
        FROM blocks b
        JOIN afdelings a ON b.afdeling_id = a.id
        JOIN estates e ON a.estate_id = e.id
        LEFT JOIN LATERAL (
            SELECT ndvi, evi, ndre, savi, gndvi, acquisition_date, cloud_cover
            FROM satellite_data
            WHERE block_id = b.id
            ORDER BY acquisition_date DESC
            LIMIT 1
        ) s ON true
        WHERE b.company_id = $1
    """
    params = [current_user["company_id"]]

    if estate_id:
        params.append(estate_id)
        query += f" AND e.id = ${len(params)}"

    if afdeling_id:
        params.append(afdeling_id)
        query += f" AND a.id = ${len(params)}"

    async with pool.acquire() as conn:
        records = await conn.fetch(query, *params)

    results = []
    for r in records:
        d = dict(r)
        if d.get("acquisition_date"):
            d["acquisition_date"] = d["acquisition_date"].isoformat()
        if isinstance(d.get("geometry"), str):
            d["geometry"] = json.loads(d["geometry"])
        results.append(d)
    return results


@router.get("/blocks/{block_id}/indices")
async def get_block_indices(
    block_id: int,
    from_date: Optional[date] = Query(None, alias="from", description="Format: YYYY-MM-DD"),
    to_date: Optional[date] = Query(None, alias="to", description="Format: YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool)
):
    async with pool.acquire() as conn:
        block = await conn.fetchrow(
            "SELECT id FROM blocks WHERE id = $1 AND company_id = $2",
            block_id, current_user["company_id"]
        )
        if not block:
            raise HTTPException(status_code=404, detail="Block not found")

        query = """
            SELECT acquisition_date, sensor, cloud_cover,
                   ndvi, evi, ndre, savi, gndvi
            FROM satellite_data
            WHERE block_id = $1
        """
        params = [block_id]

        if from_date:
            params.append(from_date)
            query += f" AND acquisition_date >= ${len(params)}"
        if to_date:
            params.append(to_date)
            query += f" AND acquisition_date <= ${len(params)}"

        query += " ORDER BY acquisition_date ASC"

        records = await conn.fetch(query, *params)

    results = []
    for r in records:
        d = dict(r)
        d["acquisition_date"] = d["acquisition_date"].isoformat() if d["acquisition_date"] else None
        results.append(d)
    return results
