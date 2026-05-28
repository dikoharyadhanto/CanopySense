"""
patcher_cloud_function.py — CanopySense Patcher-Cloud (Google Cloud Function).

Validates per-contractor API keys via Secret Manager, accepts block geometries
from request body (Option B — no outbound DB), invokes core engine, returns records.

Deploy: Google Cloud Functions (Python 3.10+, HTTP trigger)
Env vars: GCP_PROJECT_ID, SECRET_NAME, GEE_SECRET_NAME, LOG_LEVEL, FUNCTION_TIMEOUT_SECONDS
Removed in v0.9: PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD (no outbound DB).
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import pathlib
import sys
import tempfile
from datetime import date, datetime, timezone
from ipaddress import ip_address, ip_network
from typing import Any

import functions_framework
import geopandas as gpd
from google.cloud import secretmanager

logger = logging.getLogger(__name__)
_API_VERSION = "1.1"
_RASTER_SUPPORTED_INDICES: tuple[str, ...] = ("ndvi", "evi", "savi", "gndvi", "ndre")
_RASTER_SERVING_MODES: tuple[str, ...] = ("gee_mapid", "maps_platform")

_SECRET_CLIENT: secretmanager.SecretManagerServiceClient | None = None


def _get_secret_client() -> secretmanager.SecretManagerServiceClient:
    global _SECRET_CLIENT
    if _SECRET_CLIENT is None:
        _SECRET_CLIENT = secretmanager.SecretManagerServiceClient()
    return _SECRET_CLIENT


def _fetch_registry() -> dict[str, Any]:
    """Fetch API key registry; LOCAL_REGISTRY_JSON bypasses Secret Manager (local dev only)."""
    local_json = os.environ.get("LOCAL_REGISTRY_JSON", "").strip()
    if local_json:
        return json.loads(local_json)
    project_id = os.environ["GCP_PROJECT_ID"]
    secret_name = os.environ.get("SECRET_NAME", "canopysense-api-key-registry")
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = _get_secret_client().access_secret_version(request={"name": name})
    return json.loads(response.payload.data.decode("utf-8"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _ip_allowed(source_ip: str, whitelist: list[str]) -> bool:
    if not whitelist:
        return True
    try:
        addr = ip_address(source_ip)
        return any(addr in ip_network(cidr, strict=False) for cidr in whitelist)
    except ValueError:
        return False


def _audit(contractor_id: str, status: str, detail: str = "") -> None:
    logger.info(json.dumps({
        "audit": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contractor_id": contractor_id,
        "status": status,
        "detail": detail,
    }))


def _resp(body: dict, code: int) -> tuple:
    """Inject api_version into every response (success and error) before returning."""
    body.setdefault("api_version", _API_VERSION)
    return json.dumps(body), code, {"Content-Type": "application/json"}


def _fetch_gee_credentials() -> tuple[str, str, str]:
    project_id = os.environ["GCP_PROJECT_ID"]
    secret_name = os.environ.get("GEE_SECRET_NAME", "canopysense-gee-service-account")
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = _get_secret_client().access_secret_version(request={"name": name})
    key_json_str = response.payload.data.decode("utf-8")
    key_data = json.loads(key_json_str)
    return key_json_str, key_data.get("client_email", ""), key_data.get("project_id", "")


def _parse_raster_metadata_request(request) -> "dict | str":
    """Parse and validate a raster_metadata mode request body. Returns payload dict on success, error str on failure."""
    body = request.get_json(silent=True) or {}
    aoi = body.get("aoi_geojson")
    if not aoi or not isinstance(aoi, dict):
        return "400 Bad Request: Missing or invalid aoi_geojson"
    if aoi.get("type") not in ("Polygon", "MultiPolygon", "FeatureCollection"):
        return "400 Bad Request: aoi_geojson.type must be Polygon, MultiPolygon, or FeatureCollection"
    index = body.get("index")
    if index not in _RASTER_SUPPORTED_INDICES:
        return f"400 Bad Request: index must be one of {_RASTER_SUPPORTED_INDICES}"
    serving_mode = body.get("serving_mode")
    if serving_mode not in _RASTER_SERVING_MODES:
        return f"400 Bad Request: serving_mode must be one of {_RASTER_SERVING_MODES}"
    subscription_tier = body.get("subscription_tier")
    if subscription_tier not in ("basic", "premium"):
        return "400 Bad Request: subscription_tier must be 'basic' or 'premium'"
    timelapse_period_months = body.get("timelapse_period_months")
    if timelapse_period_months is not None and not isinstance(timelapse_period_months, int):
        return "400 Bad Request: timelapse_period_months must be an integer or null"
    date_start = body.get("date_start")
    date_end = body.get("date_end")
    for field_name, field_val in (("date_start", date_start), ("date_end", date_end)):
        if field_val is not None:
            try:
                date.fromisoformat(str(field_val))
            except (ValueError, TypeError):
                return f"400 Bad Request: {field_name} must be ISO date (YYYY-MM-DD)"
    return {
        "aoi_geojson": aoi,
        "index": index,
        "serving_mode": serving_mode,
        "subscription_tier": subscription_tier,
        "timelapse_period_months": timelapse_period_months,
        "date_start": date_start,
        "date_end": date_end,
    }


def _handle_raster_metadata(payload: dict) -> dict:
    """Invoke raster_engine.generate_metadata() with validated payload. Returns result dict."""
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    try:
        from raster_engine import (  # noqa: PLC0415
            generate_metadata,
            RasterEngineError,
            SubscriptionAccessError,
        )
    except ImportError as exc:
        return {"ok": False, "code": 503, "error": f"503 Service Unavailable: Raster engine not available — {exc}"}
    try:
        metadata = generate_metadata(
            index=payload["index"],
            serving_mode=payload["serving_mode"],
            subscription_tier=payload["subscription_tier"],
            timelapse_period_months=payload["timelapse_period_months"],
            aoi_geojson=payload["aoi_geojson"],
            date_start=payload["date_start"],
            date_end=payload["date_end"],
        )
        return {"ok": True, "metadata": metadata.to_dict()}
    except SubscriptionAccessError as exc:
        return {"ok": False, "code": 403, "error": f"403 Forbidden: {exc}"}
    except RasterEngineError as exc:
        return {"ok": False, "code": 503, "error": f"503 Service Unavailable: {exc}"}


def _parse_blocks(request) -> tuple[gpd.GeoDataFrame | None, Any]:
    """Parse GeoJSON FeatureCollection from request body. Returns (gdf, ids) or (None, error_str)."""
    body = request.get_json(silent=True)
    fc = (body or {}).get("blocks") if body else None
    features = (fc or {}).get("features", []) if fc else []
    if not features:
        return None, "400 Bad Request: Missing or invalid blocks payload"
    for feat in features:
        if not (feat.get("properties") or {}).get("block_id"):
            return None, "400 Bad Request: Missing block_id in feature properties"
    try:
        gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
        ids = [int(f["properties"]["block_id"]) for f in features]
        return gdf, ids
    except Exception as exc:
        logger.error("GeoDataFrame construction failed: %s", exc)
        return None, "400 Bad Request: Missing or invalid blocks payload"


def _run_engine(
    output_dir: pathlib.Path,
    blocks_gdf: gpd.GeoDataFrame,
    date_start: str | None = None,
    date_end: str | None = None,
) -> None:
    """Run engine_launcher with blocks from request body; monkey-patch output dir for /tmp write."""
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import engine_launcher  # noqa: PLC0415
    import core_engine.map_previewer as _map_previewer  # noqa: PLC0415
    output_dir.mkdir(parents=True, exist_ok=True)
    engine_launcher._OUTPUT_DIR = output_dir
    _map_previewer._DEFAULT_OUTPUT = output_dir / "canopysense_visuals.html"
    engine_launcher.run_pipeline(blocks_gdf=blocks_gdf, date_start=date_start, date_end=date_end)


def _read_records(output_dir: pathlib.Path) -> list[dict]:
    records: list[dict] = []
    for csv_path in sorted(output_dir.glob("*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as fh:
            records.extend(list(csv.DictReader(fh)))
    return records


def _build_errors(input_ids: list[int], records: list[dict]) -> list[dict]:
    """Return block_level error entries for any input block_id absent from output records."""
    output_ids = {int(r["block_id"]) for r in records}
    return [
        {"block_id": bid, "type": "block_level",
         "reason": "Block did not pass quality gate (insufficient valid pixels or no valid imagery)"}
        for bid in input_ids if bid not in output_ids
    ]


@functions_framework.http
def patcher_cloud(request):  # type: ignore[no-untyped-def]
    """CanopySense Patcher-Cloud — Cloud Function HTTP entry point."""
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] — %(message)s",
    )

    # ── 1. Require X-API-Key header ──────────────────────────────────────────
    api_key = (request.headers.get("X-API-Key") or "").strip()
    if not api_key:
        _audit("UNKNOWN", "REJECTED", "Missing X-API-Key header")
        return _resp({"error": "401 Unauthorized: Missing X-API-Key header"}, 401)

    # ── 2. Fetch registry from Secret Manager (no cache — PPX Risk 1) ────────
    try:
        registry = _fetch_registry()
    except Exception as exc:
        logger.error("Secret Manager fetch failed: %s", exc)
        return _resp({"error": "500 Internal Server Error: Registry unavailable"}, 500)

    # ── 3. Resolve contractor by key hash ────────────────────────────────────
    key_hash = _sha256(api_key)
    contractor_id: str | None = None
    record: dict = {}
    for cid, rec in registry.items():
        if rec.get("api_key_hash") == key_hash:
            contractor_id, record = cid, rec
            break

    if contractor_id is None:
        _audit("UNKNOWN", "REJECTED", "Invalid API key")
        return _resp({"error": "403 Forbidden: Invalid API Key (contact administrator)"}, 403)

    # ── 4. Check revocation ──────────────────────────────────────────────────
    if record.get("status") != "ACTIVE":
        issued = record.get("issued_date", "unknown")
        revoked = record.get("revoked_date", "unknown")
        _audit(contractor_id, "REJECTED", "Key revoked")
        return _resp(
            {"error": f"403 Forbidden: API Key revoked (issued {issued}, revoked {revoked})"},
            403,
        )

    # ── 5. Optional IP whitelist (defense-in-depth; X-Forwarded-For is advisory) ──
    whitelist = record.get("ip_whitelist", [])
    if whitelist:
        source_ip = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if not _ip_allowed(source_ip, whitelist):
            _audit(contractor_id, "REJECTED", f"IP blocked: {source_ip}")
            return _resp({"error": "403 Forbidden: Source IP not authorized"}, 403)

    # ── 6. Route by request mode ─────────────────────────────────────────────
    req_mode = (request.get_json(silent=True) or {}).get("mode")

    if req_mode == "raster_metadata":
        raster_payload = _parse_raster_metadata_request(request)
        if isinstance(raster_payload, str):
            _audit(contractor_id, "REJECTED", raster_payload)
            return _resp({"error": raster_payload}, 400)
        try:
            gee_key_json, gee_email, ee_project_id = _fetch_gee_credentials()
        except Exception as exc:
            logger.error("GEE credentials fetch failed: %s", exc)
            return _resp({"error": "500 Internal Server Error: GEE credentials unavailable"}, 500)
        os.environ["EE_SERVICE_ACCOUNT_KEY_JSON"] = gee_key_json
        os.environ["EE_SERVICE_ACCOUNT"] = gee_email
        if ee_project_id:
            os.environ["EE_PROJECT_ID"] = ee_project_id
        result = _handle_raster_metadata(raster_payload)
        if not result["ok"]:
            _audit(contractor_id, "RASTER_ERROR", result["error"])
            return _resp({"error": result["error"]}, result["code"])
        _audit(contractor_id, "RASTER_SUCCESS", f"index={raster_payload['index']} tier={raster_payload['subscription_tier']}")
        return _resp({"status": "success", "metadata": result["metadata"]}, 200)

    # ── 7. Parse and validate blocks from request body (Option B) ─────────────
    blocks_gdf, payload = _parse_blocks(request)
    if blocks_gdf is None:
        _audit(contractor_id, "REJECTED", payload)
        return _resp({"error": payload}, 400)
    input_block_ids: list[int] = payload

    # ── 8. Load GEE credentials ──────────────────────────────────────────────
    try:
        gee_key_json, gee_email, ee_project_id = _fetch_gee_credentials()
    except Exception as exc:
        logger.error("GEE credentials fetch failed: %s", exc)
        return _resp({"error": "500 Internal Server Error: GEE credentials unavailable"}, 500)
    os.environ["EE_SERVICE_ACCOUNT_KEY_JSON"] = gee_key_json
    os.environ["EE_SERVICE_ACCOUNT"] = gee_email
    if ee_project_id:
        os.environ["EE_PROJECT_ID"] = ee_project_id

    # ── 9. Invoke core engine ────────────────────────────────────────────────
    patcher_body = request.get_json(silent=True) or {}
    req_date_start: str | None = patcher_body.get("date_start")
    req_date_end: str | None = patcher_body.get("date_end")
    _audit(contractor_id, "AUTH_OK", f"Triggering core engine — {len(input_block_ids)} blocks | window={req_date_start or 'default'}→{req_date_end or 'default'}")
    timeout = int(os.environ.get("FUNCTION_TIMEOUT_SECONDS", 120))
    output_dir = pathlib.Path(tempfile.mkdtemp(prefix="cs_output_"))

    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeout

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_engine, output_dir, blocks_gdf, req_date_start, req_date_end)
        try:
            future.result(timeout=timeout)
        except FuturesTimeout:
            _audit(contractor_id, "TIMEOUT", f"Exceeded {timeout}s")
            return _resp(
                {"error": "504 Gateway Timeout: Core engine exceeded timeout (check Cloud Logging)"},
                504,
            )
        except Exception as exc:
            _audit(contractor_id, "ENGINE_ERROR", str(exc)[:500])
            return _resp(
                {"error": f"500 Internal Server Error: Core engine failed — {exc}"},
                500,
            )

    # ── 10. Return processed records + block-level error classification ────────
    records = _read_records(output_dir)
    errors = _build_errors(input_block_ids, records)
    _audit(contractor_id, "SUCCESS", f"rows={len(records)} errors={len(errors)}")

    return _resp({
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contractor_id": contractor_id,
        "rows_returned": len(records),
        "errors": errors,
        "writes": [{"table": "satellite_data",
            "columns": ["block_id","acquisition_date","sensor","cloud_cover","ndvi","evi","ndre","savi","gndvi","features"],
            "conflict_columns": ["block_id","acquisition_date","sensor"],
            "presence_check": {"block_id_column":"block_id","recency_column":"acquisition_date","recency_days":14},
            "records": records}],
    }, 200)
