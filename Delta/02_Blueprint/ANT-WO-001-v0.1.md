# ANT-WO-001-v0.1 — Work Order

> [!IMPORTANT]
> **Dependencies**: `GMN-STRAT-001-v1.0` (Strategy). **Migrated from legacy** `ANT-WO-001-v0.4`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Work Order (WO) |
| **Version** | v0.1 |
| **Status** | COMPLETE |
| **Legacy Source** | ANT-WO-001-v0.4 (2026-04-11) |
| **ANT** | Gemini (legacy) |
| **PPX Validation** | PASS (2026-04-11) |

## 2. Scope — Core Logic & Map Preview

Migration of the initial CanopySense engine: satellite extraction, cloud masking, vegetation index calculation, interactive HTML map preview, and local PostGIS ingestion.

### 2.1 Technical Tasks

1. **Maintain Core Engine Integrity** — `async_engine.py` remains unmodified.
2. **Develop `map_previewer.py`** — Utility script under `core_engine/` that imports existing engine modules to obtain the processed GEE `Image`.
3. **Tile URL Generation (All Indices)** — Use `image.getMapId()` for all 5 bands (NDVI, EVI, NDRE, SAVI, GNDVI), retrieving 5 distinct tile URLs.
4. **Leaflet HTML Template** — Generate standalone `.html` using a Leaflet.js template with `L.control.layers` for index toggling. Save to `04_Test/result_output/canopysense_visuals.html`.
5. **PostGIS Docker Integration** — Ensure CSV export + `ingest_to_postgis.py` successfully injects into local Docker PostGIS.
6. **`engine_launcher.py`** — Master orchestrator chaining extraction → preview → ingestion in one command.

### 2.2 Success Indicators

- No `ee.batch.Export.image` calls (cost avoidance)
- Standalone `.html` generated in `04_Test/result_output/`
- Leaflet layer control toggles between all 5 indices
- Docker PostGIS reports committed rows without errors
- `python 03_Build/engine_launcher.py` runs end-to-end

### 2.3 Implementation Constraints

- Python GEE API (`earthengine-api >= 0.1.418`)
- Leaflet.js via CDN (`unpkg.com/leaflet`)
- Service Account credentials reused from existing codebase

## 3. Key Design Decisions

| Decision | Choice |
| :--- | :--- |
| Extraction method | Synchronous `reduceRegions().getInfo()` (no GCS) |
| Block source | DB-first; `--seed-shapefile` for one-time initial load |
| Block unique code | `BLK-{OBJECTID:03d}` based on Shapefile OBJECTID |
| MultiPolygon handling | Largest polygon component extracted |
| Schema prefix | `ALTER ROLE postgres SET search_path` (DB-level fix) |
| Landsat NDRE | Omitted with WARNING log |
| Scheduler | Implemented but gated behind `SCHEDULER_ENABLED=false` (default) |

## 4. STR Reference

- **Linked STR**: `ANT-STR-001-v0.1`
- **Test Results**: All phases passed. UAT (Phase C) pending Director visual check.

## 5. Files Created / Modified

| Path | Action |
| :--- | :--- |
| `03_Build/core_engine/map_previewer.py` | New |
| `03_Build/engine_launcher.py` | New |
| `03_Build/requirements.txt` | Updated |
| `03_Build/ingestion/ingest_to_postgis.py` | Bug fix (1 line — ON CONFLICT columns) |

---

*Migrated from legacy `ANT-WO-001-v0.4`. For full implementation detail see `CDC-IMPL-001-v0.1`.*
