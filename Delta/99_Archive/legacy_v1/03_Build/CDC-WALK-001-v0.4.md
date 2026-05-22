# CDC-WALK-001-v0.4

> [!IMPORTANT]
> **Pre-Implementation Walkthrough** — Awaiting ANT approval before any code is written.
> Logic Dependencies: `ANT-WO-001-v0.4` / `ANT-STR-001-v0.4`

---

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Technical Walkthrough (WALK) |
| **Version** | v0.4 |
| **Status** | Approved — Implementation Complete |
| **Lead Developer** | Claude Code (CDC) |
| **Work Order Ref** | `ANT-WO-001-v0.4` |
| **Test Plan Ref** | `ANT-STR-001-v0.4` |

---

## 2. Task Interpretation

v0.4 adds three deliverables on top of the existing untouched core engine:

| # | Deliverable | Location |
| :--- | :--- | :--- |
| 1 | `map_previewer.py` | `03_Build/core_engine/` |
| 2 | `engine_launcher.py` | `03_Build/` |
| 3 | `canopysense_visuals.html` (artifact) | `04_Test/result_output/` |

`async_engine.py` and `ingest_to_postgis.py` remain **unmodified** (except Bug 2 fix — see Section 7).

**Confirmed architecture (no GCS):**
```
Shapefile (CLI arg)
  → Seed PostGIS blocks table
  → Build AOI geometry
  → GEE: scene selection → cloud mask → harmonize → calculate indices
  → synchronous reduceRegions.getInfo() → local CSV (04_Test/result_output/)
  → map_previewer: getMapId() × 5 → Leaflet HTML
  → ingest_to_postgis: CSV → canopysense.satellite_data
```

---

## 3. Shapefile Analysis (BT_BLOK_SEMBAWA)

| Property | Value |
| :--- | :--- |
| Features | 44 blocks |
| CRS | EPSG:32748 (UTM 48S) — reprojection to EPSG:4326 required |
| Estate | "Pusat Penelitian Karet Sumbawa" (1 unique value) |
| Afdelings | "Afdeling 1" (27 blocks), "Afdeling 2" (17 blocks) |
| Geometry types | 43 Polygon, 1 MultiPolygon (OBJECTID=24, Blok=2004C) |
| Block identifier | `Blok` not globally unique (29 unique for 44 rows) — use compound code |
| Clone types | "Karet", "Sawit Muda", "Lahan Kosong", null |

**Column → DB mapping:**

| Shapefile column | DB table | DB column | Notes |
| :--- | :--- | :--- | :--- |
| `estate` | `estates` | `name` | One estate per shapefile |
| — | `estates` | `code` | Generated: `"PPKS-SEMBAWA"` |
| `AfdelName` | `afdelings` | `name` | Group by afdeling |
| `Afdeling` (int) | `afdelings` | `code` | `"AFL-1"`, `"AFL-2"` |
| `Blok` | `blocks` | `name` | e.g., "2001C" |
| `OBJECTID` | `blocks` | `code` | `"BLK-{OBJECTID:03d}"` — globally unique |
| `Tahun` | `blocks` | `plant_year` | |
| `Existing` | `blocks` | `clone_type` | null allowed |
| geometry (reprojected) | `blocks` | `geometry` | Polygon only; MultiPolygon → largest component |

---

## 4. Proposed Approach

### 4.1 `engine_launcher.py`

**Entry point:** `python 03_Build/engine_launcher.py --shapefile /path/to/blocks.shp`

**Execution sequence:**

```
parse_args()                          # --shapefile (required CLI arg)
  → seed_blocks_from_shapefile()      # NEW: DB seeder (internal to launcher)
      ├─ read shapefile → reproject to EPSG:4326
      ├─ MultiPolygon → extract largest polygon component
      ├─ INSERT INTO canopysense.estates ... ON CONFLICT (code) DO NOTHING
      ├─ Compute per-afdeling union geometry
      ├─ INSERT INTO canopysense.afdelings ... ON CONFLICT DO NOTHING
      ├─ INSERT INTO canopysense.blocks ... ON CONFLICT (code) DO NOTHING
      └─ RETURN: GeoDataFrame with DB-assigned `block_id` column

  → initialize_ee()                   # existing ee_init module

  → date_start = today - 7 days      # dynamic, computed at runtime
    date_end   = today

  → aoi_ee = union of all block geometries (ee.Geometry.MultiPolygon)

  → select_best_scene(aoi_ee, date_start, date_end) → SceneResult
      └─ if scene.skip → WARNING log + graceful exit

  → apply_cloud_mask(image, sensor)
  → prepare_image(image, sensor)
  → calculate_indices(image, sensor)  # ndre skipped for Landsat

  → extract_to_local_csv()            # NEW: synchronous GEE → local CSV
      ├─ build_valid_mask_band(image)
      ├─ image.select(bands).reduceRegions(blocks_fc, mean, scale).getInfo()
      ├─ apply FR-03 quality gate in Python (valid_pixel_ratio >= 0.2)
      ├─ apply FR-08 schema formatting
      └─ write CSV to 04_Test/result_output/canopysense_{date}.csv

  → map_previewer.generate_preview()  # pass already-processed image
      └─ write 04_Test/result_output/canopysense_visuals.html

  → ingest_to_postgis.run_ingestion() # existing module (unmodified)
      └─ reads CSV → inserts into canopysense.satellite_data

  → _scheduler_stub()                 # DISABLED (SCHEDULER_ENABLED=false)
```

**Scheduler design:**
- A `run_scheduled()` function is implemented but gated behind `SCHEDULER_ENABLED` env var
- Uses `schedule` library: `schedule.every().week.do(run_pipeline)`
- When `SCHEDULER_ENABLED=false` (default), the script runs once and exits
- When enabled on a server, it runs every 7 days continuously
- The `--shapefile` path would be set as an env var `ESTATES_SHAPEFILE` for scheduled runs

---

### 4.2 `map_previewer.py`

**Function signature:**
```python
def generate_preview(
    image: ee.Image,
    sensor: str,
    aoi_ee: ee.Geometry,
    date_label: str,
    output_path: str = "04_Test/result_output/canopysense_visuals.html"
) -> str
```

**Accepts the already-processed image from the launcher** (avoids running GEE twice).
Also has a standalone `main()` for direct invocation (as WO Task 2 requires).

**Visualization parameters per band:**

| Band | Min | Max | Palette | Notes |
| :--- | :--- | :--- | :--- | :--- |
| ndvi | -0.2 | 0.9 | red → yellow → green | Standard NDVI |
| evi | -0.2 | 0.9 | red → yellow → green | |
| ndre | -0.2 | 0.9 | purple → white → green | S2 only |
| savi | -0.2 | 0.9 | brown → yellow → green | |
| gndvi | -0.2 | 0.9 | red → yellow → darkgreen | |

**NDRE Landsat handling:**
When `sensor != "S2"`: log `WARNING: NDRE not available for Landsat sensor — layer skipped`.
The NDRE entry is omitted from the `L.control.layers` overlay dict entirely.

**HTML template:** Pure Python f-string. Leaflet.js via CDN (`unpkg.com/leaflet`).
Layer Control with all available indices as overlays. Map centered on AOI centroid.

---

## 5. Files to Create / Modify

| File | Action | Purpose |
| :--- | :--- | :--- |
| `03_Build/engine_launcher.py` | **NEW** | Master orchestrator + DB seeder + sync GEE extract |
| `03_Build/core_engine/map_previewer.py` | **NEW** | HTML map preview via getMapId() |
| `04_Test/result_output/` | EXISTS (created) | Output directory for HTML and CSV |
| `04_Test/.env` | EXISTS (created) | PostGIS + GEE credentials |
| `03_Build/ingestion/ingest_to_postgis.py` | **BUG FIX ONLY** | Fix Bug 2 only (2 lines) — see Section 7 |
| `03_Build/core_engine/async_engine.py` | **ZERO CHANGE** | GCS export path — preserved, untouched |

---

## 6. Dependencies

| Package | Status | Use |
| :--- | :--- | :--- |
| `earthengine-api >= 0.1.418` | Already in requirements.txt | GEE API + getMapId() |
| `geopandas >= 0.14` | Already in requirements.txt | Shapefile reading + reprojection |
| `psycopg2` | Already in requirements.txt | PostGIS seeding + ingestion |
| `pandas >= 2.0` | Already in requirements.txt | CSV building |
| `python-dotenv` | Already in requirements.txt | .env loading |
| `schedule` | **NEW — add to requirements.txt** | Weekly scheduler stub |
| Leaflet.js | CDN only, no pip install | HTML map frontend |

---

## 7. Bug Fix Required in `ingest_to_postgis.py`

The WO mandates `ingest_to_postgis.py` remain "completely unmodified and functional."
The current code has Bug 2 which makes it non-functional against the actual DB schema:

| Bug | Current code | Required fix |
| :--- | :--- | :--- |
| Bug 1 — schema prefix | `satellite_data` | Fixed at DB level via `ALTER ROLE postgres SET search_path TO canopysense, public` — **already applied, no code change** |
| Bug 2 — wrong conflict columns | `ON CONFLICT (block_id, acquisition_date)` | `ON CONFLICT (block_id, acquisition_date, sensor)` |

The DB has `UNIQUE(block_id, acquisition_date, sensor)` (3-column constraint). PostgreSQL
will raise `ERROR: there is no unique or exclusion constraint matching the ON CONFLICT specification`
on every insert. Phase D cannot pass without this fix.

**This is a 1-line change in `ingest_to_postgis.py` line 291.**

**ANT DECISION REQUIRED**: Grant permission to apply Bug 2 fix before implementation begins.

---

## 8. DB Seeding Logic — estates constraint note

`estates.geometry` is `GEOMETRY(MultiPolygonZ, 4326)` with a validity CHECK.
The estate union geometry will be derived from the block polygons unioned per estate.
For the seeder, this geometry will be cast from the block union (2D → 3D with Z=0).

---

## 9. Flags Resolution Summary

| Flag | Status | Resolution |
| :--- | :--- | :--- |
| FLAG 1 — NDRE Landsat | ✅ RESOLVED | Skip layer + WARNING log |
| FLAG 2 — No GCS | ✅ RESOLVED | Sync reduceRegions → local CSV |
| FLAG 3 — Shapefile input | ✅ RESOLVED | `--shapefile` CLI arg |
| FLAG 3 — Date range | ✅ RESOLVED | Dynamic: today - 7 days |
| FLAG 3 — Scheduler | ✅ RESOLVED | Stub code, `SCHEDULER_ENABLED=false` |
| FLAG 3 — Credentials | ✅ RESOLVED | postgres/postgres, .env created |
| Bug 1 — Schema prefix | ✅ RESOLVED (DB level) | `ALTER ROLE postgres SET search_path` applied |
| Bug 2 — Conflict columns | ⏳ AWAITING PERMISSION | 1-line fix in ingest_to_postgis.py |
| blocks table empty | ✅ RESOLVED | engine_launcher seeds DB from shapefile (Option A) |

---

## 10. Pre-Implementation Summary

**All design decisions are resolved. Ready to implement upon ANT approval of:**
1. This walkthrough document
2. Permission to apply Bug 2 fix (1 line in `ingest_to_postgis.py`)

**CDC will not begin coding until both are explicitly approved.**
