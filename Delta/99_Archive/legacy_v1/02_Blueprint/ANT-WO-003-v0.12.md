---
name: ANT-WO-003-v0.12
project: Canopy Sense
phase: Tahap III — Spatial Decision Support: GEE Viewer Endpoint
status: ON HOLD — Director decision 2026-04-25: feature scope unconfirmed; pending stakeholder validation before implementation proceeds
version: 0.12
created_date: 2026-04-25
prerequisite: ANT-WO-003-v0.10 COMPLETE, ANT-STR-003-v0.10 ALL PHASES PASSED
supersedes: ANT-WO-003-v0.11 (obsolete — HTML blob storage approach dropped)
inputs:
  - PPX-CONV-003-v0.11.1.md (architecture verification Q1–Q4)
  - GPT Audit — CanopySense v0.11 GEE Viewer (product framing)
---

# ANT-WO-003-v0.12 (Work Order)

> [!IMPORTANT]
> **Lead Developer (CDC):** This Work Order is purely additive. Zero changes to `patcher_cloud_function.py`, `patcher_local.py`, or any existing patcher infrastructure. All work is a new Cloud Function file and an adaptation to `map_previewer.py`.

---

## 1. Background and Motivation

**The gap (GPT audit finding):**
CanopySense has two map layers: a PostGIS block-alert map and a GEE raster map. The raster is currently positioned as a data viewer — it shows NDVI values but gives no directional guidance. When a field inspector sees an alert on the main map, they have no way to identify *where within the block* the problem is located.

**GPT's product verdict:** A pure raster viewer will fail to be adopted. The feature must function as a decision support tool — giving inspectors a highlighted problem zone and a coverage metric, not just a raster to stare at.

**Why not store HTML or tile configs in PostGIS (PPX Q1–Q2 finding):**
GEE tile URLs from `getMapId()` expire in ~48h. Storing them creates stale data. On-demand generation always produces valid tiles. Data consistency (required for audit/compliance — PPX Q1) is achieved by filtering GEE by the exact `acquisition_date` stored in `satellite_data` — the same date as the patcher run, so the viewer always reflects exactly what was patched.

**The fix (v0.12):**
A new read-only Cloud Function endpoint (`viewer_cloud`) that:
1. Accepts `block_id` and optional params
2. Queries PostGIS for block geometry and latest patched `acquisition_date`
3. Reconstructs exact GEE imagery using that date
4. Returns a JSON config with two Leaflet tile layers (NDVI raster + threshold problem mask) and a coverage stat
5. The UI team embeds this JSON in the main map as a drill-down panel when an inspector clicks a problematic block

**Patcher is complete and untouched.** The viewer is a read concern, not a write concern.

---

## 2. Director Decision Flags

Read all flags before approving this WO. FLAGS A and E are blocking — ANT cannot issue this WO to CDC without answers. FLAGS B, C, D, F, G are non-blocking but will affect the WO revision if overridden.

---

> **FLAG-A — BLOCKING: Default NDVI threshold for "problem area"**
>
> The threshold mask highlights pixels where NDVI falls below a defined value. This is the core of the decision support layer. Tropical plantation benchmarks suggest NDVI < 0.4 as stressed canopy (severe stress/bare) and < 0.5 as moderate stress. This is estate-type dependent (oil palm vs rubber vs mixed).
>
> **ANT proposes: `0.4` as hardcoded default.**
>
> Director must confirm or override this value before CDC implements.
>
> Options:
> - Confirm 0.4
> - Set a different value
> - Ask agronomist / defer default until field trial

---

> **FLAG-B — BLOCKING: Is the threshold configurable per request?**
>
> Should the `/viewer` endpoint accept a `?threshold=` query parameter so the frontend or inspector can adjust sensitivity without a CDC code change?
>
> **ANT recommends: YES** — single optional param, zero extra complexity, enables a threshold slider in the UI without touching CDC code.
>
> Options:
> - YES — configurable via `?threshold=` (ANT recommendation)
> - NO — hardcoded default only

---

> **FLAG-C — INPUT REQUESTED: Include problem area in hectares?**
>
> The stats response can include `problem_area_ha` computed from PostGIS geometry (`ST_Area(geometry::geography) / 10000 × coverage_pct / 100`). Field inspectors benefit from knowing how much physical area to cover. One extra PostGIS function call — no GEE impact.
>
> **ANT recommends: YES** — small cost, high field value.
>
> Options:
> - YES — include `problem_area_ha` in stats
> - NO — percentage only

---

> **FLAG-D — INPUT REQUESTED: Vegetation index scope for v0.12**
>
> The viewer plans to highlight NDVI only (single threshold mask). EVI and NDRE are available from the same GEE pipeline. Each additional index requires one more `getMapId()` call (+1–2s latency per index per PPX Q4 benchmark).
>
> **ANT recommends: NDVI only for v0.12.** Multi-index toggle deferred to v0.13.
>
> Override if Director wants multi-index in v0.12 — ANT will adjust the line budget and STR accordingly.

---

> **FLAG-E — BLOCKING: Viewer endpoint authentication model**
>
> The viewer Cloud Function is read-only but exposes proprietary estate NDVI data and geometry. Should it use the same X-API-Key mechanism (Secret Manager registry) as the patcher?
>
> **ANT recommends: YES — same X-API-Key.** Avoids a public read endpoint that exposes estate spatial data. The UI frontend already handles the key for the patcher; reusing it adds no friction.
>
> Options:
> - Same X-API-Key via Secret Manager (ANT recommendation)
> - Open / no auth (simpler for frontend dev, security risk)
> - Separate viewer-specific API key (more granular, more management overhead)

---

> **FLAG-F — INPUT REQUESTED: Clustering of problem zones**
>
> GPT audit mentioned "optional AI clustering" — grouping adjacent low-NDVI pixels into labeled zones (Zone 1, Zone 2) for easier field navigation. Significant GEE implementation complexity (connected component analysis or `reduceToVectors()`).
>
> **ANT recommends: Defer to v0.13.** v0.12 delivers the threshold mask; clustering is a follow-on.
>
> Override if Director wants clustering in v0.12 — scope and line budget will change significantly.

---

> **FLAG-G — INPUT REQUESTED: Data warning trigger condition**
>
> When should the response include a non-null `data_warning` string? Candidates are drawn from values already stored in `satellite_data`:
> - `cloud_cover > 30` (stored as float in `satellite_data`)
> - `valid_pixel_ratio < 0.7` (stored in `features` JSONB)
>
> **ANT recommends: Trigger if `cloud_cover > 30 OR valid_pixel_ratio < 0.7`.** Frontend displays a banner ("imagery quality low — results may be unreliable"). Does not block the viewer — still returns 200.
>
> Override if Director wants a different threshold or wants to suppress warnings entirely.

---

## 3. Technical Tasks (Scope)

### 3.1 `deploy/core_engine/map_previewer.py` — Add `get_viewer_config()`

Add one new function alongside the existing `generate_preview()`. **`generate_preview()` must remain completely unchanged** — `engine_launcher` calls it during patcher runs. Any change to its signature or return value risks breaking the patcher pipeline.

**New function:**

```python
def get_viewer_config(
    block_geometry: dict,     # GeoJSON geometry dict of the block
    acquisition_date: str,    # ISO date string — exact date from satellite_data
    sensor: str,              # e.g. "sentinel-2"
    threshold: float,         # Problem area NDVI threshold — see FLAG-A
) -> dict:
```

**Behavior:**
1. Initialize `ee.Geometry` from `block_geometry`
2. Filter Sentinel-2 SR ImageCollection by `acquisition_date` (±1 day window) and block bounds — use `.first()` if multiple scenes match
3. Compute NDVI from filtered image
4. Call `getMapId()` for NDVI raster — palette red → yellow → green, min=−1, max=1
5. Create problem mask: `ndvi.lt(threshold)`, masked where not problem
6. Call `getMapId()` for problem mask — solid highlight color (Director to confirm via FLAG-A or leave CDC default)
7. Call `reduceRegion()` on NDVI image within block geometry — scale=10 (Sentinel-2 native), compute mean NDVI and problem pixel percentage
8. Check FLAG-G warning condition (cloud_cover and valid_pixel_ratio passed in by caller)
9. Return dict — schema below

**Return schema:**
```python
{
    "layers": {
        "ndvi": {
            "tile_url": str,
            "min": -1,
            "max": 1,
            "palette": ["red", "yellow", "green"]
        },
        "problem_mask": {
            "tile_url": str,
            "threshold": float,
            "description": str   # e.g. "Areas with NDVI below 0.4"
        }
    },
    "bounds": [[lat_min, lon_min], [lat_max, lon_max]],  # Leaflet-compatible
    "stats": {
        "problem_coverage_pct": float,
        "mean_ndvi": float,
        "problem_area_ha": float | None    # FLAG-C decision
    },
    "data_warning": str | None             # FLAG-G decision
}
```

---

### 3.2 New `viewer_cloud_function.py`

**File:** `03_Build/viewer_cloud_function.py`
**Line limit:** ≤200 lines
**Deploy sync:** `03_Build/deploy_viewer/main.py`

**Request contract:**
```
GET <viewer_url>
Headers:
  X-API-Key: <key>                  (if FLAG-E = same X-API-Key)
Query params:
  block_id           integer    required
  threshold          float      optional, default = FLAG-A value    (if FLAG-B = YES)
  acquisition_date   date       optional, default = latest from satellite_data
```

**Processing flow (in order):**
1. Auth: validate X-API-Key via Secret Manager registry — same `_fetch_registry()` + `_sha256()` pattern as patcher (see Note 4)
2. Parse and validate `block_id` — 400 if missing or non-integer
3. Parse optional `threshold` — 400 if present but not a valid float in [0, 1]
4. Parse optional `acquisition_date` — 400 if present but not a valid ISO date
5. Connect to PostGIS via env vars (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD)
6. Query `canopysense.blocks`: `SELECT ST_AsGeoJSON(geometry) FROM canopysense.blocks WHERE id = %s` — 404 if no row
7. Query `canopysense.satellite_data`: latest (or specified) `acquisition_date`, `sensor`, `cloud_cover`, `features` for this `block_id` — 404 with message "No patched data for this block — run patcher first" if no row
8. Parse `features` JSONB for FLAG-G warning evaluation
9. Init GEE via `_fetch_gee_credentials()` — same pattern as patcher (see Note 4)
10. Call `map_previewer.get_viewer_config(geometry, acquisition_date, sensor, threshold)`
11. Return JSON response

**Success response (200):**
```json
{
  "status": "success",
  "api_version": "1.0",
  "block_id": 18,
  "acquisition_date": "2026-04-18",
  "sensor": "sentinel-2",
  "threshold": 0.4,
  "layers": {
    "ndvi": {
      "tile_url": "...",
      "min": -1,
      "max": 1,
      "palette": ["red", "yellow", "green"]
    },
    "problem_mask": {
      "tile_url": "...",
      "threshold": 0.4,
      "description": "Areas with NDVI below 0.4"
    }
  },
  "bounds": [[-1.1, 108.0], [-1.0, 108.1]],
  "stats": {
    "problem_coverage_pct": 34.2,
    "mean_ndvi": 0.52,
    "problem_area_ha": null
  },
  "data_warning": null,
  "generated_at": "2026-04-25T21:00:00Z"
}
```

**Error responses — all must include `api_version`:**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid X-API-Key |
| 403 | Key revoked |
| 400 | Missing `block_id` or invalid param value |
| 404 | `block_id` not in `canopysense.blocks` |
| 404 | No rows in `satellite_data` for this block |
| 500 | PostGIS connection failure or GEE credential error |
| 504 | GEE `get_viewer_config()` exceeded timeout |

---

### 3.3 `03_Build/deploy_viewer/` Directory

New source directory for the viewer Cloud Function deployment. Lean subset — no engine_launcher, no full GEE pipeline.

```
03_Build/deploy_viewer/
  main.py                       (sync of viewer_cloud_function.py)
  requirements.txt
  core_engine/
    __init__.py
    map_previewer.py             (adapted — with get_viewer_config() added)
    ee_init.py                   (GEE initialization — copied from deploy/)
```

**`requirements.txt` for viewer:**
```
functions-framework>=3.0.0
google-cloud-secret-manager>=2.16.0
earthengine-api>=0.1.418
geopandas>=0.14
psycopg2-binary>=2.9
```

No `pandas`, no `schedule`, no `engine_launcher` dependencies.

---

### 3.4 Patcher — Zero Changes Confirmed

`patcher_cloud_function.py`, `patcher_local.py`, `deploy/main.py`, `deploy/core_engine/` (except `map_previewer.py` — additive only) — **no modifications to existing functions or logic**.

---

## 4. Success Indicators

| Indicator | How to Verify |
|-----------|--------------|
| `GET /viewer?block_id=18` returns 200 with full JSON structure | curl |
| `layers.ndvi.tile_url` loads in browser as Leaflet-compatible tile | Browser check |
| `layers.problem_mask.tile_url` renders colored overlay on problem areas | Visual inspection |
| `acquisition_date` in response matches `satellite_data` for that block | PostGIS cross-check |
| `stats.problem_coverage_pct` is float between 0 and 100 | JSON assertion |
| `GET /viewer?block_id=9999` returns 404 | curl |
| `GET /viewer` with no key returns 401 | curl |
| Response time ≤7s for single block | `curl -w %{time_total}` |
| `generate_preview()` in `map_previewer.py` still produces HTML file | Run engine_launcher locally |
| `patcher_cloud_function.py` line count: 254 | `wc -l` |
| `patcher_local.py` line count: 300 | `wc -l` |

---

## 5. Implementation Constraints

| Constraint | Rule |
|-----------|------|
| `viewer_cloud_function.py` | ≤200 lines |
| `map_previewer.py` | `generate_preview()` signature and behavior unchanged; `get_viewer_config()` is additive only |
| `patcher_cloud_function.py` | No changes — stays at 254 lines |
| `patcher_local.py` | No changes — stays at 300 lines |
| GEE image reconstruction | Must filter by exact `acquisition_date` from `satellite_data` — not "latest available imagery" |
| PostGIS connection in viewer | Same env var pattern as patcher (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD) |
| `deploy_viewer/` | No `engine_launcher.py`, no `async_engine.py`, no `ingestion/` — viewer does not run the full GEE pipeline |
| Tile URL generation | `getMapId()` only — no batch export, no asset creation |
| Timeout ceiling | 300s — same FUNCTION_TIMEOUT_SECONDS pattern |
| Sensor support | Sentinel-2 only in v0.12 (scale=10m for `reduceRegion()`) |

---

## 6. Deliverables Checklist

| Deliverable | Type | Owner | Status |
|------------|------|-------|--------|
| `deploy/core_engine/map_previewer.py` | Modify — add `get_viewer_config()` only | CDC | Pending |
| `03_Build/viewer_cloud_function.py` | New file | CDC | Pending |
| `03_Build/deploy_viewer/main.py` | New file (sync) | CDC | Pending |
| `03_Build/deploy_viewer/requirements.txt` | New file | CDC | Pending |
| `03_Build/deploy_viewer/core_engine/` | New directory (lean copy) | CDC | Pending |
| `03_Build/CDC-IMPL-003-v0.12.md` | Implementation log | CDC | Pending |

---

## 7. Notes for CDC

1. **`generate_preview()` is untouchable.** `engine_launcher` calls it in the patcher run pipeline. `get_viewer_config()` is a sibling function in the same file — different signature, different purpose, zero overlap.

2. **GEE image reconstruction accuracy.** Use `.filterDate(acquisition_date, acquisition_date_plus_one_day).filterBounds(block_geometry).first()`. This reproduces the scene closest to what the patcher used. `.first()` prevents failure if the date boundary returns two partial scenes.

3. **`getMapId()` tile URL validity.** URLs are valid for the GEE session lifetime (~48h). Since the viewer regenerates on every request, expiry is a non-issue.

4. **Reuse auth patterns — do not rewrite.** `_fetch_registry()`, `_sha256()`, `_fetch_gee_credentials()`, and `_get_secret_client()` from `patcher_cloud_function.py` must be copied verbatim or factored into a shared utility. Do not reinvent these. If they are duplicated, note this in `CDC-IMPL-003-v0.12.md` as a known limitation to be resolved in a future shared-lib WO.

5. **PostGIS geometry query.** Use `ST_AsGeoJSON(geometry)::json` to get a Python dict directly from psycopg2. This avoids string parsing before passing to `ee.Geometry`.

6. **`deploy_viewer/` is a lean copy.** Only include `map_previewer.py`, `ee_init.py`, `__init__.py` in `core_engine/`. Do not copy `async_engine.py`, `cloud_masking.py`, `harmonization.py`, `index_calculator.py`, `quality_gate.py`, `scene_selector.py` — the viewer does not need the full pipeline.

7. **`api_version` for viewer is `"1.0"`.** This is the viewer's own version, not the patcher's `"1.1"`. They are independent endpoints.

---

**ANT Sign-off**: PENDING — awaiting Director decisions on FLAG-A, FLAG-B, FLAG-E (blocking) and FLAG-C, FLAG-D, FLAG-F, FLAG-G (input requested).

**Next Steps (after Director decisions):**
1. Director provides flag answers
2. ANT revises WO with confirmed values — removes flag blocks, sets concrete defaults
3. CDC submits `CDC-WALK-003-v0.12.md`
4. ANT approves walkthrough
5. CDC implements and submits `CDC-IMPL-003-v0.12.md`
6. ANT executes `ANT-STR-003-v0.12`
