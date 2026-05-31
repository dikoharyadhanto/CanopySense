"""
estate_onboarding.py — Admin estate and data onboarding endpoints.

Permission model:
  - Admin + Super-admin: all routes
  - Manager: 403 on all routes (enforced by get_current_admin dep)

Routes:
  GET  /companies/{company_id}/estates          — list estates for a company
  POST /companies/{company_id}/estates          — create estate metadata stub
  GET  /estates/{estate_id}                     — estate detail + afdelings + blocks sample
  PATCH /estates/{estate_id}                    — edit name/code (is_draft=TRUE only)
  POST /estates/{estate_id}/import/parse        — parse GeoJSON to features for map preview, no DB writes
  POST /estates/{estate_id}/import/preview      — validate GeoJSON, no spatial writes
  POST /estates/{estate_id}/import/commit       — transactional insert of afdelings + blocks
"""
from __future__ import annotations

import json
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.api.deps import get_current_admin
from app.api.admin.audit_log import log_admin_action
from app.database import get_db_pool, settings
from app.services.spatial_validator import (
    validate_geojson_bytes,
    run_postgis_validity,
    run_db_duplicate_check,
    convert_to_geojson_bytes,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class EstateCreate(BaseModel):
    name: str
    code: str


class EstateEdit(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /companies/{company_id}/estates
# ---------------------------------------------------------------------------

@router.get("/companies/{company_id}/estates")
async def list_estates(
    company_id: int,
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        company = await conn.fetchrow(
            "SELECT id FROM public.companies WHERE id = $1", company_id
        )
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        rows = await conn.fetch(
            """
            SELECT
                e.id,
                e.name,
                e.code,
                e.is_draft,
                e.created_at,
                COUNT(DISTINCT a.id)  AS afdeling_count,
                COUNT(DISTINCT b.id)  AS block_count
            FROM canopysense.estates e
            LEFT JOIN canopysense.afdelings a ON a.estate_id = e.id
            LEFT JOIN canopysense.blocks     b ON b.afdeling_id = a.id
            WHERE e.company_id = $1
            GROUP BY e.id
            ORDER BY e.created_at DESC
            """,
            company_id,
        )
    return {"items": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# POST /companies/{company_id}/estates
# ---------------------------------------------------------------------------

@router.post("/companies/{company_id}/estates", status_code=201)
async def create_estate(
    company_id: int,
    body: EstateCreate,
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    name = body.name.strip()
    code = body.code.strip().upper()

    if not name:
        raise HTTPException(status_code=422, detail="Estate name must not be empty")
    if not code:
        raise HTTPException(status_code=422, detail="Estate code must not be empty")
    if len(code) > 20:
        raise HTTPException(status_code=422, detail="Estate code must be 20 characters or fewer")
    if len(name) > 100:
        raise HTTPException(status_code=422, detail="Estate name must be 100 characters or fewer")

    async with pool.acquire() as conn:
        company = await conn.fetchrow(
            "SELECT id FROM public.companies WHERE id = $1", company_id
        )
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        try:
            row = await conn.fetchrow(
                """
                INSERT INTO canopysense.estates (name, code, company_id, geometry, is_draft)
                VALUES ($1, $2, $3, NULL, TRUE)
                RETURNING id, name, code, company_id, is_draft, created_at
                """,
                name,
                code,
                company_id,
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=409,
                detail=f"Estate code {code!r} already exists",
            )

        await log_admin_action(
            conn,
            actor_id=user["id"],
            action="estate_create",
            target_type="estate",
            target_id=row["id"],
            metadata={"name": row["name"], "code": row["code"], "company_id": company_id},
        )

    return dict(row)


# ---------------------------------------------------------------------------
# GET /estates/{estate_id}
# ---------------------------------------------------------------------------

@router.get("/estates/{estate_id}")
async def get_estate_detail(
    estate_id: int,
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        estate = await conn.fetchrow(
            """
            SELECT
                e.id, e.name, e.code, e.company_id, e.is_draft, e.created_at,
                c.company_name
            FROM canopysense.estates e
            JOIN public.companies c ON c.id = e.company_id
            WHERE e.id = $1
            """,
            estate_id,
        )
        if estate is None:
            raise HTTPException(status_code=404, detail="Estate not found")

        afdelings = await conn.fetch(
            """
            SELECT a.id, a.name, a.code, COUNT(b.id) AS block_count
            FROM canopysense.afdelings a
            LEFT JOIN canopysense.blocks b ON b.afdeling_id = a.id
            WHERE a.estate_id = $1
            GROUP BY a.id
            ORDER BY a.code
            """,
            estate_id,
        )
        blocks_sample = await conn.fetch(
            """
            SELECT b.id, b.name, b.code, b.plant_year, b.clone_type,
                   a.code AS afdeling_code
            FROM canopysense.blocks b
            JOIN canopysense.afdelings a ON a.id = b.afdeling_id
            WHERE a.estate_id = $1
            ORDER BY b.code
            LIMIT 20
            """,
            estate_id,
        )

    afd_list = [dict(a) for a in afdelings]
    return {
        **dict(estate),
        "afdelings": afd_list,
        "blocks_sample": [dict(b) for b in blocks_sample],
        "afdeling_count": len(afd_list),
        "block_count": sum(int(a["block_count"]) for a in afd_list),
    }


# ---------------------------------------------------------------------------
# PATCH /estates/{estate_id}
# ---------------------------------------------------------------------------

@router.patch("/estates/{estate_id}")
async def edit_estate(
    estate_id: int,
    body: EstateEdit,
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    if body.name is None and body.code is None:
        raise HTTPException(
            status_code=422,
            detail="At least one field (name or code) must be provided",
        )

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Estate name must not be empty")
        if len(name) > 100:
            raise HTTPException(
                status_code=422, detail="Estate name must be 100 characters or fewer"
            )
    else:
        name = None

    if body.code is not None:
        code = body.code.strip().upper()
        if not code:
            raise HTTPException(status_code=422, detail="Estate code must not be empty")
        if len(code) > 20:
            raise HTTPException(
                status_code=422, detail="Estate code must be 20 characters or fewer"
            )
    else:
        code = None

    async with pool.acquire() as conn:
        estate = await conn.fetchrow(
            "SELECT id, name, code, company_id, is_draft FROM canopysense.estates WHERE id = $1",
            estate_id,
        )
        if estate is None:
            raise HTTPException(status_code=404, detail="Estate not found")
        if not estate["is_draft"]:
            raise HTTPException(
                status_code=409,
                detail="Committed estates cannot be edited via this endpoint",
            )

        if code is not None and code != estate["code"]:
            conflict = await conn.fetchrow(
                """
                SELECT id FROM canopysense.estates
                WHERE company_id = $1 AND code = $2 AND id != $3
                """,
                estate["company_id"],
                code,
                estate_id,
            )
            if conflict:
                raise HTTPException(
                    status_code=409,
                    detail=f"Estate code {code!r} already exists in this company",
                )

        new_name = name if name is not None else estate["name"]
        new_code = code if code is not None else estate["code"]

        updated = await conn.fetchrow(
            """
            UPDATE canopysense.estates SET name = $1, code = $2
            WHERE id = $3
            RETURNING id, name, code, company_id, is_draft, created_at
            """,
            new_name,
            new_code,
            estate_id,
        )

        await log_admin_action(
            conn,
            actor_id=user["id"],
            action="estate_edit",
            target_type="estate",
            target_id=estate_id,
            metadata={
                "old_name": estate["name"],
                "old_code": estate["code"],
                "new_name": new_name,
                "new_code": new_code,
            },
        )

    return dict(updated)


# ---------------------------------------------------------------------------
# POST /estates/{estate_id}/import/parse
# ---------------------------------------------------------------------------

@router.post("/estates/{estate_id}/import/parse")
async def import_parse(
    estate_id: int,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        estate = await conn.fetchrow(
            "SELECT id FROM canopysense.estates WHERE id = $1",
            estate_id,
        )
    if estate is None:
        raise HTTPException(status_code=404, detail="Estate not found")

    file_bytes = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1)
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds maximum upload size ({settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB)",
        )
    filename = file.filename or "upload.geojson"

    conversion_warnings: list[str] = []
    lower_ext = filename.lower()
    if lower_ext.endswith('.zip') or lower_ext.endswith('.kml') or lower_ext.endswith('.kmz'):
        try:
            file_bytes, conversion_warnings = convert_to_geojson_bytes(file_bytes, filename)
            filename = filename.rsplit('.', 1)[0] + '.geojson'
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    # Use validate_geojson_bytes only for structural error detection (invalid JSON,
    # wrong FeatureCollection type, unsupported CRS). Do NOT filter by property
    # validity here — the frontend column mapper needs all features with their
    # original property names so it can offer column remapping.
    result = validate_geojson_bytes(file_bytes, filename)
    all_warnings = conversion_warnings + result.warnings

    if result.file_error:
        return {"features": [], "warnings": [result.file_error] + all_warnings}

    try:
        data = json.loads(file_bytes)
    except Exception:
        return {"features": [], "warnings": all_warnings}

    features = []
    for f in (data.get("features") or []):
        if not isinstance(f, dict) or f.get("type") != "Feature":
            continue
        geom = f.get("geometry")
        if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": f.get("properties") or {},
        })

    return {"features": features, "warnings": all_warnings}


# ---------------------------------------------------------------------------
# POST /estates/{estate_id}/import/preview
# ---------------------------------------------------------------------------

@router.post("/estates/{estate_id}/import/preview")
async def import_preview(
    estate_id: int,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        estate = await conn.fetchrow(
            "SELECT id, company_id FROM canopysense.estates WHERE id = $1",
            estate_id,
        )
    if estate is None:
        raise HTTPException(status_code=404, detail="Estate not found")

    # Reject oversized uploads before reading into memory (DoS/memory-exhaustion prevention)
    file_bytes = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1)
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds maximum upload size ({settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB)",
        )
    filename = file.filename or "upload.geojson"

    # Convert Shapefile/KML/KMZ to GeoJSON before validation
    conversion_warnings: list[str] = []
    lower_ext = filename.lower()
    if lower_ext.endswith('.zip') or lower_ext.endswith('.kml') or lower_ext.endswith('.kmz'):
        try:
            file_bytes, conversion_warnings = convert_to_geojson_bytes(file_bytes, filename)
            filename = filename.rsplit('.', 1)[0] + '.geojson'
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    # Phase 1: Python validation
    result = validate_geojson_bytes(file_bytes, filename)
    result.warnings = conversion_warnings + result.warnings

    if result.file_error:
        async with pool.acquire() as conn:
            await log_admin_action(
                conn,
                actor_id=user["id"],
                action="estate_import_preview",
                target_type="estate",
                target_id=estate_id,
                metadata={
                    "filename": filename,
                    "file_error": result.file_error,
                    "commit_eligible": False,
                },
            )
        return {
            "commit_eligible": False,
            "file_error": result.file_error,
            "valid_blocks": [],
            "invalid_rows": [],
            "afdeling_count": 0,
            "warnings": result.warnings,
        }

    # Phase 2: PostGIS validity batch check (read-only)
    postgis_invalid = await run_postgis_validity(result.valid_features, pool)
    postgis_invalid_idxs = {i["index"] for i in postgis_invalid}
    postgis_valid = [f for f in result.valid_features if f["_idx"] not in postgis_invalid_idxs]

    # Phase 2b: DB duplicate block_code check (read-only)
    db_duplicates = await run_db_duplicate_check(postgis_valid, pool)
    db_dup_idxs = {i["index"] for i in db_duplicates}
    valid_final = [f for f in postgis_valid if f["_idx"] not in db_dup_idxs]

    all_invalid = sorted(
        result.invalid_rows + postgis_invalid + db_duplicates,
        key=lambda x: x["index"],
    )

    commit_eligible = len(all_invalid) == 0 and len(valid_final) > 0
    afdeling_codes = {str(f["properties"]["afdeling_code"]) for f in valid_final}

    async with pool.acquire() as conn:
        await log_admin_action(
            conn,
            actor_id=user["id"],
            action="estate_import_preview",
            target_type="estate",
            target_id=estate_id,
            metadata={
                "filename": filename,
                "valid_count": len(valid_final),
                "invalid_count": len(all_invalid),
                "commit_eligible": commit_eligible,
            },
        )

    return {
        "commit_eligible": commit_eligible,
        "file_error": None,
        "valid_blocks": [
            {
                "index": f["_idx"],
                "block_code": f["properties"]["block_code"],
                "block_name": f["properties"]["block_name"],
                "afdeling_code": f["properties"]["afdeling_code"],
                "afdeling_name": f["properties"]["afdeling_name"],
                "plant_year": f["properties"].get("plant_year"),
                "clone_type": f["properties"].get("clone_type"),
            }
            for f in valid_final
        ],
        "invalid_rows": all_invalid,
        "afdeling_count": len(afdeling_codes),
        "warnings": result.warnings,
    }


# ---------------------------------------------------------------------------
# POST /estates/{estate_id}/import/commit
# ---------------------------------------------------------------------------

@router.post("/estates/{estate_id}/import/commit")
async def import_commit(
    estate_id: int,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        estate = await conn.fetchrow(
            "SELECT id, company_id FROM canopysense.estates WHERE id = $1",
            estate_id,
        )
    if estate is None:
        raise HTTPException(status_code=404, detail="Estate not found")

    company_id = estate["company_id"]

    # Reject oversized uploads before reading into memory (DoS/memory-exhaustion prevention)
    file_bytes = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1)
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds maximum upload size ({settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB)",
        )
    filename = file.filename or "upload.geojson"

    # Convert Shapefile/KML/KMZ to GeoJSON before validation
    lower_ext = filename.lower()
    if lower_ext.endswith('.zip') or lower_ext.endswith('.kml') or lower_ext.endswith('.kmz'):
        try:
            file_bytes, _ = convert_to_geojson_bytes(file_bytes, filename)
            filename = filename.rsplit('.', 1)[0] + '.geojson'
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    # Phase 1: Python validation (same path as preview — no trust in client state)
    result = validate_geojson_bytes(file_bytes, filename)

    if result.file_error:
        async with pool.acquire() as conn:
            await log_admin_action(
                conn,
                actor_id=user["id"],
                action="estate_import_failure",
                target_type="estate",
                target_id=estate_id,
                metadata={"filename": filename, "reason": result.file_error},
            )
        raise HTTPException(status_code=422, detail=result.file_error)

    # Phase 2: PostGIS validity batch check
    postgis_invalid = await run_postgis_validity(result.valid_features, pool)
    postgis_invalid_idxs = {i["index"] for i in postgis_invalid}
    postgis_valid = [
        f for f in result.valid_features if f["_idx"] not in postgis_invalid_idxs
    ]

    all_phase2_invalid = result.invalid_rows + postgis_invalid
    if all_phase2_invalid:
        async with pool.acquire() as conn:
            await log_admin_action(
                conn,
                actor_id=user["id"],
                action="estate_import_failure",
                target_type="estate",
                target_id=estate_id,
                metadata={
                    "filename": filename,
                    "reason": "Validation failed",
                    "invalid_count": len(all_phase2_invalid),
                },
            )
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Validation failed — file is not commit-eligible",
                "invalid_rows": sorted(all_phase2_invalid, key=lambda x: x["index"]),
            },
        )

    # Phase 2b: DB duplicate check before opening transaction
    db_duplicates = await run_db_duplicate_check(postgis_valid, pool)
    if db_duplicates:
        async with pool.acquire() as conn:
            await log_admin_action(
                conn,
                actor_id=user["id"],
                action="estate_import_failure",
                target_type="estate",
                target_id=estate_id,
                metadata={
                    "filename": filename,
                    "reason": "DB block_code conflict",
                    "duplicate_codes": [d["block_code"] for d in db_duplicates],
                },
            )
        raise HTTPException(
            status_code=409,
            detail={
                "message": "block_code conflict: codes already exist in database",
                "invalid_rows": db_duplicates,
            },
        )

    valid_features = postgis_valid

    # Group features by afdeling_code
    afdeling_map: dict[str, dict] = {}
    for feat in valid_features:
        props = feat["properties"]
        acode = str(props["afdeling_code"])
        if acode not in afdeling_map:
            afdeling_map[acode] = {
                "name": str(props["afdeling_name"]),
                "code": acode,
                "features": [],
            }
        afdeling_map[acode]["features"].append(feat)

    afdelings_created = 0
    blocks_created = 0

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Safety net: re-check DB duplicates inside transaction
                all_codes = [str(f["properties"]["block_code"]) for f in valid_features]
                existing = await conn.fetch(
                    "SELECT code FROM canopysense.blocks WHERE code = ANY($1::text[])",
                    all_codes,
                )
                if existing:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "message": "block_code conflict detected inside transaction",
                            "codes": [r["code"] for r in existing],
                        },
                    )

                # Fetch existing afdelings for this estate
                existing_afds = await conn.fetch(
                    "SELECT id, code FROM canopysense.afdelings WHERE estate_id = $1",
                    estate_id,
                )
                existing_afd_map = {r["code"]: r["id"] for r in existing_afds}
                afdeling_id_map: dict[str, int] = {}

                for acode, afd in afdeling_map.items():
                    if acode in existing_afd_map:
                        await conn.execute(
                            "UPDATE canopysense.afdelings SET name = $1 WHERE id = $2",
                            afd["name"],
                            existing_afd_map[acode],
                        )
                        afdeling_id_map[acode] = existing_afd_map[acode]
                    else:
                        afd_row = await conn.fetchrow(
                            """
                            INSERT INTO canopysense.afdelings
                                (name, code, estate_id, company_id, geometry)
                            VALUES ($1, $2, $3, $4, NULL)
                            RETURNING id
                            """,
                            afd["name"],
                            acode,
                            estate_id,
                            company_id,
                        )
                        afdeling_id_map[acode] = afd_row["id"]
                        afdelings_created += 1

                # Insert blocks
                for feat in valid_features:
                    props = feat["properties"]
                    acode = str(props["afdeling_code"])
                    await conn.execute(
                        """
                        INSERT INTO canopysense.blocks
                            (name, code, afdeling_id, company_id,
                             plant_year, clone_type, geometry)
                        VALUES ($1, $2, $3, $4, $5, $6, ST_GeomFromGeoJSON($7))
                        """,
                        str(props["block_name"]),
                        str(props["block_code"]),
                        afdeling_id_map[acode],
                        company_id,
                        props.get("plant_year"),
                        str(props["clone_type"]) if props.get("clone_type") else None,
                        json.dumps(feat["geometry"]),
                    )
                    blocks_created += 1

                # Update afdeling geometries: union of their committed blocks
                for acode, afdeling_id in afdeling_id_map.items():
                    await conn.execute(
                        """
                        UPDATE canopysense.afdelings
                        SET geometry = (
                            SELECT ST_Multi(ST_Union(b.geometry))
                            FROM canopysense.blocks b
                            WHERE b.afdeling_id = $1
                        )
                        WHERE id = $1
                        """,
                        afdeling_id,
                    )

                # Update estate geometry and mark as committed
                await conn.execute(
                    """
                    UPDATE canopysense.estates
                    SET
                        geometry = (
                            SELECT ST_Force3D(ST_Multi(ST_Union(b.geometry)))
                            FROM canopysense.blocks b
                            JOIN canopysense.afdelings a ON a.id = b.afdeling_id
                            WHERE a.estate_id = $1
                        ),
                        is_draft = FALSE
                    WHERE id = $1
                    """,
                    estate_id,
                )

                # Audit log inside the same transaction
                await log_admin_action(
                    conn,
                    actor_id=user["id"],
                    action="estate_import_commit",
                    target_type="estate",
                    target_id=estate_id,
                    metadata={
                        "filename": filename,
                        "afdelings_created": afdelings_created,
                        "blocks_created": blocks_created,
                    },
                )

    except HTTPException:
        # Raised inside the transaction (safety-net duplicate) — write failure audit
        async with pool.acquire() as conn:
            await log_admin_action(
                conn,
                actor_id=user["id"],
                action="estate_import_failure",
                target_type="estate",
                target_id=estate_id,
                metadata={"filename": filename, "reason": "DB conflict inside transaction"},
            )
        raise
    except asyncpg.UniqueViolationError as exc:
        async with pool.acquire() as conn:
            await log_admin_action(
                conn,
                actor_id=user["id"],
                action="estate_import_failure",
                target_type="estate",
                target_id=estate_id,
                metadata={"filename": filename, "reason": str(exc)},
            )
        raise HTTPException(
            status_code=409, detail=f"Unique constraint violation: {exc}"
        )

    return {
        "estate_id": estate_id,
        "afdelings_created": afdelings_created,
        "blocks_created": blocks_created,
    }
