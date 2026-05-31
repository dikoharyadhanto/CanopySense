from __future__ import annotations

import json
from pathlib import Path

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.admin.audit_log import log_admin_action
from app.api.deps import get_current_super_admin
from app.database import get_db_pool
from app.services.spatial_validator import convert_to_geojson_bytes, validate_geojson_bytes

router = APIRouter()

UPLOADS_BASE = Path(__file__).resolve().parent.parent.parent.parent / "uploads"


# ─── GET /admin/estate-change-requests ───────────────────────────────────────
# TASK-007

@router.get("/estate-change-requests")
async def list_estate_change_requests(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    pool: asyncpg.Pool = Depends(get_db_pool),
    _user: dict = Depends(get_current_super_admin),
):
    offset = (page - 1) * page_size
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT c.id AS company_id, c.company_name, cs.estate_change_status,
                       cs.estate_change_requested_at, cs.estate_change_reject_reason,
                       cs.estate_change_file_path
                FROM company_settings cs
                JOIN companies c ON c.id = cs.company_id
                WHERE cs.estate_change_status = $1
                ORDER BY cs.estate_change_requested_at DESC NULLS LAST
                LIMIT $2 OFFSET $3
                """,
                status.upper(), page_size, offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM company_settings WHERE estate_change_status = $1",
                status.upper(),
            )
        else:
            rows = await conn.fetch(
                """
                SELECT c.id AS company_id, c.company_name, cs.estate_change_status,
                       cs.estate_change_requested_at, cs.estate_change_reject_reason,
                       cs.estate_change_file_path
                FROM company_settings cs
                JOIN companies c ON c.id = cs.company_id
                WHERE cs.estate_change_status != 'NONE'
                ORDER BY cs.estate_change_requested_at DESC NULLS LAST
                LIMIT $1 OFFSET $2
                """,
                page_size, offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM company_settings WHERE estate_change_status != 'NONE'"
            )

    return {"items": [dict(r) for r in rows], "total": total, "page": page, "page_size": page_size}


# ─── GET /admin/estate-change-requests/{company_id}/preview ──────────────────
# TASK-008: return GeoJSON FeatureCollection for map preview

@router.get("/estate-change-requests/{company_id}/preview")
async def preview_estate_change_request(
    company_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
    _user: dict = Depends(get_current_super_admin),
):
    async with pool.acquire() as conn:
        cs = await conn.fetchrow(
            "SELECT estate_change_status, estate_change_file_path FROM company_settings WHERE company_id = $1",
            company_id,
        )

    if not cs:
        raise HTTPException(status_code=404, detail="Company settings not found")
    if not cs["estate_change_file_path"]:
        raise HTTPException(status_code=404, detail="No estate change file on record")

    ec_file = UPLOADS_BASE.parent / cs["estate_change_file_path"]
    if not ec_file.exists():
        raise HTTPException(status_code=404, detail="Estate change file not found on disk")

    file_bytes = ec_file.read_bytes()
    try:
        data = json.loads(file_bytes)
    except Exception:
        raise HTTPException(status_code=422, detail="Stored file is not valid JSON")

    features = []
    for f in (data.get("features") or []):
        if not isinstance(f, dict) or f.get("type") != "Feature":
            continue
        geom = f.get("geometry")
        if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        features.append({"type": "Feature", "geometry": geom, "properties": f.get("properties") or {}})

    return {"type": "FeatureCollection", "features": features}


# ─── POST /admin/estate-change-requests/{company_id}/approve ─────────────────
# TASK-009

@router.post("/estate-change-requests/{company_id}/approve")
async def approve_estate_change(
    company_id: int,
    pool: asyncpg.Pool = Depends(get_db_pool),
    user: dict = Depends(get_current_super_admin),
):
    async with pool.acquire() as conn:
        cs = await conn.fetchrow(
            "SELECT estate_change_status, estate_change_file_path FROM company_settings WHERE company_id = $1",
            company_id,
        )

    if not cs or cs["estate_change_status"] != "PENDING":
        raise HTTPException(status_code=400, detail="No pending estate change request for this company")

    ec_file = UPLOADS_BASE.parent / cs["estate_change_file_path"]
    if not ec_file.exists():
        raise HTTPException(status_code=422, detail="Estate change file not found on disk")

    file_bytes = ec_file.read_bytes()
    try:
        data = json.loads(file_bytes)
    except Exception:
        raise HTTPException(status_code=422, detail="Stored file is not valid JSON")

    features = [
        f for f in (data.get("features") or [])
        if isinstance(f, dict)
        and f.get("type") == "Feature"
        and isinstance(f.get("geometry"), dict)
        and f["geometry"].get("type") in ("Polygon", "MultiPolygon")
    ]
    if not features:
        raise HTTPException(status_code=422, detail="No valid features found in stored file")

    # Group features by afdeling_code
    afdeling_map: dict[str, dict] = {}
    for feat in features:
        props = feat.get("properties") or {}
        acode = str(props.get("afdeling_code", "DEFAULT"))
        if acode not in afdeling_map:
            afdeling_map[acode] = {
                "name": str(props.get("afdeling_name", acode)),
                "code": acode,
                "features": [],
            }
        afdeling_map[acode]["features"].append(feat)

    async with pool.acquire() as conn:
        # Get the company's active estate
        estate = await conn.fetchrow(
            "SELECT id FROM canopysense.estates WHERE company_id = $1 AND is_active = TRUE LIMIT 1",
            company_id,
        )
        if not estate:
            raise HTTPException(status_code=422, detail="Company has no active estate to replace")
        estate_id = estate["id"]

        # Get manager email + company name for notification
        manager_row = await conn.fetchrow(
            """SELECT u.email, u.full_name, c.company_name
               FROM users u
               JOIN canopysense.companies c ON c.id = u.company_id
               WHERE u.company_id = $1 AND u.role = 'manager' LIMIT 1""",
            company_id,
        )

        async with conn.transaction():
            # Archive old afdelings and blocks (soft-delete)
            await conn.execute(
                """
                UPDATE canopysense.blocks
                SET is_active = FALSE, archived_at = NOW()
                WHERE company_id = $1 AND is_active = TRUE
                """,
                company_id,
            )
            await conn.execute(
                """
                UPDATE canopysense.afdelings
                SET is_active = FALSE, archived_at = NOW()
                WHERE company_id = $1 AND is_active = TRUE
                """,
                company_id,
            )

            afdelings_created = 0
            blocks_created = 0
            afdeling_id_map: dict[str, int] = {}

            for acode, afd in afdeling_map.items():
                afd_row = await conn.fetchrow(
                    """
                    INSERT INTO canopysense.afdelings
                        (name, code, estate_id, company_id, geometry, is_active)
                    VALUES ($1, $2, $3, $4, NULL, TRUE)
                    RETURNING id
                    """,
                    afd["name"], acode, estate_id, company_id,
                )
                afdeling_id_map[acode] = afd_row["id"]
                afdelings_created += 1

            for feat in features:
                props = feat.get("properties") or {}
                acode = str(props.get("afdeling_code", "DEFAULT"))
                # ON CONFLICT: if same block code exists (archived), restore it with new data
                await conn.execute(
                    """
                    INSERT INTO canopysense.blocks
                        (name, code, afdeling_id, company_id, plant_year, clone_type, geometry, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6, ST_GeomFromGeoJSON($7), TRUE)
                    ON CONFLICT (code) DO UPDATE SET
                        name       = EXCLUDED.name,
                        afdeling_id = EXCLUDED.afdeling_id,
                        company_id = EXCLUDED.company_id,
                        plant_year = EXCLUDED.plant_year,
                        clone_type = EXCLUDED.clone_type,
                        geometry   = EXCLUDED.geometry,
                        is_active  = TRUE,
                        archived_at = NULL
                    """,
                    str(props.get("block_name", "")),
                    str(props.get("block_code", "")),
                    afdeling_id_map[acode],
                    company_id,
                    props.get("plant_year"),
                    str(props["clone_type"]) if props.get("clone_type") else None,
                    json.dumps(feat["geometry"]),
                )
                blocks_created += 1

            # Update afdeling geometries
            for acode, afdeling_id in afdeling_id_map.items():
                await conn.execute(
                    """
                    UPDATE canopysense.afdelings
                    SET geometry = (
                        SELECT ST_Multi(ST_Union(b.geometry))
                        FROM canopysense.blocks b
                        WHERE b.afdeling_id = $1 AND b.is_active = TRUE
                    )
                    WHERE id = $1
                    """,
                    afdeling_id,
                )

            # Update estate geometry
            await conn.execute(
                """
                UPDATE canopysense.estates
                SET geometry = (
                    SELECT ST_Force3D(ST_Multi(ST_Union(b.geometry)))
                    FROM canopysense.blocks b
                    JOIN canopysense.afdelings a ON a.id = b.afdeling_id
                    WHERE a.estate_id = $1 AND b.is_active = TRUE
                ),
                is_draft = FALSE
                WHERE id = $1
                """,
                estate_id,
            )

            # Mark request as approved
            await conn.execute(
                """
                UPDATE company_settings
                SET estate_change_status = 'APPROVED', estate_change_reject_reason = NULL, updated_at = NOW()
                WHERE company_id = $1
                """,
                company_id,
            )

            await log_admin_action(
                conn, user["id"], "estate_change_approve", "company", company_id,
                {"afdelings_created": afdelings_created, "blocks_created": blocks_created},
            )

    # Send email to manager (non-blocking)
    if manager_row and manager_row["email"]:
        try:
            from app.services.email import send_estate_change_approved_email
            await send_estate_change_approved_email(
                manager_row["email"],
                manager_row["full_name"] or "Manager",
                manager_row["company_name"] or "",
            )
        except Exception:
            pass

    return {"approved": True, "afdelings_created": afdelings_created, "blocks_created": blocks_created}


# ─── POST /admin/estate-change-requests/{company_id}/reject ──────────────────
# TASK-010

class RejectEstateChangeRequest(BaseModel):
    reason: str


@router.post("/estate-change-requests/{company_id}/reject")
async def reject_estate_change(
    company_id: int,
    body: RejectEstateChangeRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
    user: dict = Depends(get_current_super_admin),
):
    async with pool.acquire() as conn:
        cs = await conn.fetchrow(
            "SELECT estate_change_status FROM company_settings WHERE company_id = $1",
            company_id,
        )

    if not cs or cs["estate_change_status"] != "PENDING":
        raise HTTPException(status_code=400, detail="No pending estate change request for this company")

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE company_settings
            SET estate_change_status = 'REJECTED', estate_change_reject_reason = $2, updated_at = NOW()
            WHERE company_id = $1
            """,
            company_id, body.reason,
        )

        manager_row = await conn.fetchrow(
            """SELECT u.email, u.full_name, c.company_name
               FROM users u
               JOIN canopysense.companies c ON c.id = u.company_id
               WHERE u.company_id = $1 AND u.role = 'manager' LIMIT 1""",
            company_id,
        )

        await log_admin_action(
            conn, user["id"], "estate_change_reject", "company", company_id,
            {"reason": body.reason},
        )

    if manager_row and manager_row["email"]:
        try:
            from app.services.email import send_estate_change_rejected_email
            await send_estate_change_rejected_email(
                manager_row["email"],
                manager_row["full_name"] or "Manager",
                manager_row["company_name"] or "",
                body.reason,
            )
        except Exception:
            pass

    return {"rejected": True, "reason": body.reason}
