# ANT-STR-001-v0.1 — Test Plan (STR)

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-001-v0.1`. **Migrated from legacy** `ANT-STR-001-v0.4`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Test Plan (STR) |
| **Version** | v0.1 |
| **Status** | COMPLETE |

## 2. Test Phases

| Phase | Action | Pass Criteria | Result |
| :--- | :--- | :--- | :---: |
| A | Code review — no `ee.batch.Export.image` in `map_previewer.py` | No export commands; `getMapId()` called | ✅ |
| B | Run `python 03_Build/engine_launcher.py` | CSV + HTML generated, all steps chain | ✅ |
| C | Visual Acceptance — open `canopysense_visuals.html` in browser | Leaflet map loads; layer control toggles all indices | ⏳ Pending UAT |
| D | PostGIS ingestion | Committed rows reported; no schema errors | ✅ |

## 3. Execution Results (2026-04-11)

| Item | Result |
| :--- | :--- |
| Scene | Sentinel-2 Tier 1 (2026-04-06) |
| Scene valid_pixel_ratio | 0.756 |
| Blocks passed FR-03 gate | 3 of 44 (41 skipped — below 0.2 threshold) |
| CSV output | `canopysense_2026-04-06.csv` (3 rows) |
| HTML output | `canopysense_visuals.html` (5 tile layers) |
| satellite_data rows | block_id 22, 35, 36 — sentinel-2 |
| Errors | 0 |

---

*Migrated from legacy `ANT-STR-001-v0.4`.*
