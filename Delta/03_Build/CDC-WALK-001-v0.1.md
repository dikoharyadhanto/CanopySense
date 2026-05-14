# CDC-WALK-001-v0.1 — Technical Walkthrough

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-001-v0.1`. **Migrated from legacy** `CDC-WALK-001-v0.4`.

## 1. Metadata

| Field             | Value                              |
|:----------------- |:---------------------------------- |
| **Project ID**    | 001                                |
| **Document Type** | Walkthrough (WALK)                 |
| **Version**       | v0.1                               |
| **Status**        | APPROVED — Implementation Complete |

## 2. Task Interpretation

Add three deliverables to the existing core engine:

| #   | Deliverable                           | Location                 |
|:--- |:------------------------------------- |:------------------------ |
| 1   | `map_previewer.py`                    | `core_engine/` (new)     |
| 2   | `engine_launcher.py`                  | `03_Build/` (new)        |
| 3   | `canopysense_visuals.html` (artifact) | `04_Test/result_output/` |

**Architecture:** No GCS. All extraction via synchronous `reduceRegions().getInfo()`.

## 3. Shapefile Analysis — BT_BLOK_SEMBAWA

| Property  | Value                                          |
|:--------- |:---------------------------------------------- |
| Features  | 44 blocks                                      |
| CRS       | EPSG:32748 → EPSG:4326                         |
| Estate    | "Pusat Penelitian Karet Sumbawa"               |
| Afdelings | Afdeling 1 (27 blocks), Afdeling 2 (17 blocks) |
| Geometry  | 43 Polygon, 1 MultiPolygon                     |

## 4. Map Preview Pipeline

```
generate_preview(image, sensor, aoi_ee, date_label)
  ├─ determine bands: [ndvi, evi, savi, gndvi] + [ndre if S2]
  ├─ aoi_ee.centroid().getInfo()     → map center
  ├─ image.select(band).getMapId()   → tile_url per band
  └─ _render_html()                  → Leaflet template → .html
```

## 5. Bug Fix — `ingest_to_postgis.py` (1 line)

ON CONFLICT target changed from `(block_id, acquisition_date)` to `(block_id, acquisition_date, sensor)` to match the actual DB UNIQUE constraint. Approved by ANT.

## 6. Files Created / Modified

| File                                      | Action                                               |
|:----------------------------------------- |:---------------------------------------------------- |
| `03_Build/core_engine/map_previewer.py`   | New                                                  |
| `03_Build/engine_launcher.py`             | New                                                  |
| `03_Build/requirements.txt`               | Added `psycopg2-binary`, `python-dotenv`, `schedule` |
| `03_Build/core_engine/__init__.py`        | Updated API                                          |
| `03_Build/ingestion/ingest_to_postgis.py` | Bug fix (1 line)                                     |
| `04_Test/.env`                            | New                                                  |
| `04_Test/result_output/`                  | Created (output directory)                           |

## 7. Technical Debt

- `_gdf_to_ee_feature_collection` is O(N) — fine at 44 blocks, revisit at 10k+
- Leaflet tile URLs expire in ~48h — intentional per WO for engineering preview
- Shapefile column schema dependency — different shapefiles may require adjustment

---

*Migrated from legacy `CDC-WALK-001-v0.4`.*
