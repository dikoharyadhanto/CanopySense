---
name: ANT-WO-002-v0.5
project: Canopy Sense
phase: Tahap I (Backfill): Historical Data Seeding
status: COMPLETED / IMPLEMENTED
ppx_validation: PASS (Required for STL & ML training)
ppx_validation_date: 2026-04-11
---

# ANT-WO-002-v0.5 (Work Order)

> [!IMPORTANT]
> **Lead Developer (Claude Code)**: You are granted "Freedom of Method" within the constraints of this Work Order.
> Goal: Create a new script to loop backward up to 3 years (or as far back as available data permits) to extract historical indices (NDVI, NDRE, EVI, SAVI, GNDVI) from Sentinel-2 and Landsat.
> The 3-year historical baseline is intended to capture at least 3 full annual cycles of vegetation indices, which is typical for robust seasonal-trend decomposition and anomaly detection in tropical agriculture.

## 1. Technical Tasks (Scope)

1. **Develop `historical_backfill.py`**:
   - Create the script under `03_Build/historical_backfill.py` or equivalent folder.
   - The script must loop backward to fetch up to 3 years of imagery history (April 2023 - April 2026), or as far back as available data permits for the specified blocks.
   - Process both Sentinel-2 and Landsat data seamlessly to cover cloud gaps.
   - Use time-chunking logic (e.g. 30-day or 1-month chunks) to ensure Earth Engine `reduceRegions` does not fail due to memory timeouts.

2. **Database Integration**:
   - Output the raw CSV logs into `04_Test/result_output/historical/` to keep them organized.
   - The script must push the data chunks directly into the local Docker PostGIS `satellite_data` table using the existing `ON CONFLICT DO NOTHING` logic via `ingest_to_postgis.py`.

## 2. Success Indicators

- [ ] Chunking logic successfully runs without Earth Engine timeouts.
- [ ] Terminal logs display successful batch inserts into the PostgreSQL database.
- [ ] No duplicate errors in PostGIS due to overlapping dates.
- [ ] `04_Test/result_output/historical/` contains all generated CSV backups.

## 3. Implementation Constraints

- **Re-use existing code**: Pull components from `async_engine.py` (like `scene_selector`, `cloud_masking`, `index_calculator`). Do not write new logic for cloud masking or rendering.
- **Logging**: Ensure the progress is printed tracking the month being processed (e.g., `Processing chunk: Jan 2024...`).

---
**ANT (Technical Foreman) Sign-off**: 2026-04-11 (v0.5)
