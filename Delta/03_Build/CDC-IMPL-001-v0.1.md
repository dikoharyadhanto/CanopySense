# CDC-IMPL-001-v0.1 — Implementation Log

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-001-v0.1`. **Migrated from legacy** `CDC-IMPL-001-v0.4`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Implementation Log (IMPL) |
| **Version** | v0.1 |
| **Status** | COMPLETE |
| **CDC** | Claude Code (legacy) |

## 2. Files Created

| Path | Purpose |
| :--- | :--- |
| `core_engine/map_previewer.py` | GEE `getMapId()` tile preview + Leaflet HTML generator |
| `engine_launcher.py` | Master orchestrator: seed → GEE extract → preview → ingest |

## 3. Technical Decisions

| # | Decision | Rationale |
| :--- | :--- | :--- |
| 1 | Synchronous `reduceRegions().getInfo()` | No GCS; fast at 44 blocks |
| 2 | DB-first block loading | Shapefile only for one-time seed |
| 3 | `BLK-{OBJECTID:03d}` as block code | OBJECTID is globally unique |
| 4 | Largest polygon for MultiPolygon | Satisfies PostGIS `GeometryType='POLYGON'` constraint |
| 5 | DB-level schema fix (`ALTER ROLE SET search_path`) | No Python changes needed |
| 6 | 1-line ON CONFLICT fix in `ingest_to_postgis.py` | Bug fix approved by ANT |
| 7 | NDRE skipped for Landsat with WARNING | No Red Edge band on Landsat |
| 8 | Actual acquisition date from scene image | Replaces stale `date_start` tech debt |
| 9 | Scheduler stub behind `SCHEDULER_ENABLED` flag | Weekly automation code present but dormant |
| 10 | `ST_Force3D(ST_Multi(…))` for geometry insert | Satisfies `MultiPolygonZ, 4326` column type |

## 4. Pipeline Flow

```
engine_launcher.py
  ├─ _seed_blocks_from_shapefile()   [if --seed-shapefile]
  ├─ _load_blocks_from_db()          → GeoDataFrame
  ├─ initialize_ee()
  ├─ select_best_scene()             → SceneResult
  ├─ apply_cloud_mask() → prepare_image() → calculate_indices()
  ├─ _extract_to_local_csv()         → reduceRegions().getInfo()
  ├─ generate_preview()              → getMapId() × 5 → Leaflet HTML
  └─ run_ingestion()                 → satellite_data INSERT
```

## 5. Test Results

| Phase | Result |
| :--- | :---: |
| Phase A — Code review | ✅ |
| Phase B — Execution | ✅ |
| Phase C — Visual UAT | ⏳ Pending Director |
| Phase D — PostGIS | ✅ |

---

*Migrated from legacy `CDC-IMPL-001-v0.4`.*
