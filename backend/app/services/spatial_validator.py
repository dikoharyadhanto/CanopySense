"""
spatial_validator.py — Two-phase GeoJSON validation for estate block import.

Phase 1 (Python, no DB): file size, JSON parse, FeatureCollection type, CRS
metadata, feature geometry type, required properties, field lengths,
plant_year type, within-file duplicate block_code detection.

Phase 2 (PostGIS, read-only batch query): ST_IsValid + ST_IsValidReason for
all candidate features that passed Phase 1.

A separate helper (run_db_duplicate_check) checks block_codes against the live
DB. The preview handler calls all three. The commit handler calls all three
again before opening a transaction — no reliance on prior preview state.
"""
import json
from dataclasses import dataclass, field
from typing import List, Optional

import asyncpg


_ACCEPTED_CRS_NAMES: set[str] = {
    "urn:ogc:def:crs:OGC:1.3:CRS84",
    "urn:ogc:def:crs:EPSG::4326",
    "EPSG:4326",
}

_MAX_FIELD_LENGTHS: dict[str, int] = {
    "block_code": 20,
    "block_name": 100,
    "afdeling_code": 20,
    "afdeling_name": 100,
    "clone_type": 50,
}

_REQUIRED_PROPS = ("block_code", "block_name", "afdeling_code", "afdeling_name")


@dataclass
class ValidationResult:
    valid_features: List[dict] = field(default_factory=list)
    invalid_rows: List[dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    commit_eligible: bool = False
    file_error: Optional[str] = None


def validate_geojson_bytes(
    file_bytes: bytes,
    filename: str,
    max_bytes: int = 10 * 1024 * 1024,
) -> ValidationResult:
    """Phase 1 validation — pure Python, no DB calls."""
    result = ValidationResult()

    if len(file_bytes) > max_bytes:
        result.file_error = (
            f"File too large: {len(file_bytes):,} bytes (max {max_bytes:,})"
        )
        return result

    lower = filename.lower()
    if not (lower.endswith(".geojson") or lower.endswith(".json")):
        result.file_error = "Unsupported file type: must be .geojson or .json"
        return result

    try:
        data = json.loads(file_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        result.file_error = f"Invalid JSON: {exc}"
        return result

    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        result.file_error = "File must be a GeoJSON FeatureCollection"
        return result

    crs_obj = data.get("crs")
    if crs_obj is not None:
        crs_name = _extract_crs_name(crs_obj)
        if crs_name not in _ACCEPTED_CRS_NAMES:
            result.file_error = (
                f"Unsupported CRS: file must use WGS84 / EPSG:4326 (got {crs_name!r}). "
                "Remove the 'crs' member or use urn:ogc:def:crs:OGC:1.3:CRS84."
            )
            return result

    features = data.get("features")
    if not isinstance(features, list) or len(features) == 0:
        result.file_error = "File contains no features (empty file)"
        return result

    if len(features) > 5000:
        result.warnings.append(
            f"Large file: {len(features)} features. Import may take several seconds."
        )

    # Pre-scan for duplicate block_codes to flag all occurrences (not just second)
    code_occurrences: dict[str, list[int]] = {}
    for idx, feat in enumerate(features):
        props = feat.get("properties") or {} if isinstance(feat, dict) else {}
        code = props.get("block_code")
        if code is not None:
            key = str(code)
            code_occurrences.setdefault(key, []).append(idx)
    duplicate_codes: set[str] = {
        code for code, idxs in code_occurrences.items() if len(idxs) > 1
    }

    # Per-feature validation
    for idx, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            result.invalid_rows.append(
                {"index": idx, "block_code": None, "reason": "Not a valid GeoJSON Feature"}
            )
            continue

        errs: list[str] = []
        geom = feature.get("geometry")

        if geom is None:
            errs.append("Missing geometry")
        elif not isinstance(geom, dict) or geom.get("type") != "Polygon":
            got = geom.get("type") if isinstance(geom, dict) else type(geom).__name__
            errs.append(
                f"Geometry must be Polygon (got {got!r}; MultiPolygon is not accepted)"
            )

        props = feature.get("properties") or {}

        for prop in _REQUIRED_PROPS:
            val = props.get(prop)
            if val is None or not str(val).strip():
                errs.append(f"Missing or empty required property: '{prop}'")

        for prop, max_len in _MAX_FIELD_LENGTHS.items():
            val = props.get(prop)
            if val is not None and len(str(val)) > max_len:
                errs.append(
                    f"Property '{prop}' exceeds max length {max_len} "
                    f"(got {len(str(val))})"
                )

        plant_year = props.get("plant_year")
        if plant_year is not None and not isinstance(plant_year, int):
            errs.append(
                f"Property 'plant_year' must be an integer "
                f"(got {type(plant_year).__name__!r})"
            )

        block_code = str(props.get("block_code", "")).strip()
        if not errs and block_code and block_code in duplicate_codes:
            errs.append(f"Duplicate block_code within file: {block_code!r}")

        if errs:
            result.invalid_rows.append(
                {
                    "index": idx,
                    "block_code": props.get("block_code"),
                    "reason": "; ".join(errs),
                }
            )
        else:
            result.valid_features.append(
                {"_idx": idx, "geometry": geom, "properties": props}
            )

    result.commit_eligible = (
        len(result.invalid_rows) == 0 and len(result.valid_features) > 0
    )
    return result


def _extract_crs_name(crs_obj: object) -> Optional[str]:
    """Extract a canonical CRS name string from a GeoJSON crs member."""
    if isinstance(crs_obj, str):
        return crs_obj
    if isinstance(crs_obj, dict):
        props = crs_obj.get("properties")
        if isinstance(props, dict):
            return props.get("name")
        return crs_obj.get("name") or crs_obj.get("href")
    return None


async def run_postgis_validity(
    valid_features: list[dict],
    pool: asyncpg.Pool,
) -> list[dict]:
    """Phase 2 — PostGIS ST_IsValid batch check (read-only, no transaction).

    Returns list of invalid-feature dicts: {index, block_code, reason}.
    """
    if not valid_features:
        return []

    geom_jsons = [json.dumps(f["geometry"]) for f in valid_features]

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                ordinality AS idx,
                ST_IsValid(ST_GeomFromGeoJSON(feature_geom)) AS is_valid,
                ST_IsValidReason(ST_GeomFromGeoJSON(feature_geom)) AS reason
            FROM unnest($1::text[]) WITH ORDINALITY AS t(feature_geom, ordinality)
            """,
            geom_jsons,
        )

    invalid: list[dict] = []
    for row in rows:
        if not row["is_valid"]:
            feat = valid_features[int(row["idx"]) - 1]  # ordinality is 1-based
            invalid.append(
                {
                    "index": feat["_idx"],
                    "block_code": feat["properties"].get("block_code"),
                    "reason": f"Invalid geometry: {row['reason']}",
                }
            )
    return invalid


async def run_db_duplicate_check(
    valid_features: list[dict],
    pool: asyncpg.Pool,
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict]:
    """Check block_codes against existing blocks table.

    Returns list of duplicate-dicts: {index, block_code, reason}.
    Can accept an already-open connection (for use inside a transaction).
    """
    if not valid_features:
        return []

    codes = [str(f["properties"]["block_code"]) for f in valid_features]

    async def _check(c: asyncpg.Connection) -> list[dict]:
        existing = await c.fetch(
            "SELECT code FROM canopysense.blocks WHERE code = ANY($1::text[])",
            codes,
        )
        existing_set = {r["code"] for r in existing}
        return [
            {
                "index": feat["_idx"],
                "block_code": str(feat["properties"]["block_code"]),
                "reason": (
                    f"block_code already exists in database: "
                    f"{feat['properties']['block_code']!r}"
                ),
            }
            for feat in valid_features
            if str(feat["properties"]["block_code"]) in existing_set
        ]

    if conn is not None:
        return await _check(conn)
    async with pool.acquire() as c:
        return await _check(c)
