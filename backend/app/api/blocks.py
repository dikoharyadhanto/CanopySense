from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
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
        SELECT b.id, b.code, b.name, b.plant_year, b.clone_type,
               ST_AsGeoJSON(b.geometry)::jsonb as geometry,
               a.name as afdeling_name, e.name as estate_name
        FROM blocks b
        JOIN afdelings a ON b.afdeling_id = a.id
        JOIN estates e ON a.estate_id = e.id
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
        
    return [dict(r) for r in records]

@router.get("/blocks/{block_id}/indices")
async def get_block_indices(
    block_id: int,
    start_date: Optional[str] = Query(None, description="Format: YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Format: YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool)
):
    # Verify block belongs to company
    async with pool.acquire() as conn:
        block = await conn.fetchrow("SELECT id FROM blocks WHERE id = $1 AND company_id = $2", block_id, current_user["company_id"])
        if not block:
            raise HTTPException(status_code=404, detail="Block not found")
            
        query = """
            SELECT acquisition_date, sensor, cloud_cover, ndvi, evi, ndre, savi, gndvi, features
            FROM satellite_data
            WHERE block_id = $1
        """
        params = [block_id]
        
        if start_date:
            params.append(start_date)
            query += f" AND acquisition_date >= ${len(params)}::date"
        if end_date:
            params.append(end_date)
            query += f" AND acquisition_date <= ${len(params)}::date"
            
        query += " ORDER BY acquisition_date DESC"
        
        records = await conn.fetch(query, *params)
        
    # Format dates correctly
    results = []
    for r in records:
        d = dict(r)
        d['acquisition_date'] = d['acquisition_date'].isoformat() if d['acquisition_date'] else None
        if isinstance(d.get('features'), str):
            try:
                d['features'] = json.loads(d['features'])
            except:
                pass
        results.append(d)
        
    return results
