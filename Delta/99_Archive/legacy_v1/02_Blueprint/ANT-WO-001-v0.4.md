---
name: ANT-WO-001-v0.4
project: Canopy Sense
phase: Tahap I: Ekstraksi Data, Cloud Masking & Rumus Indeks (Visual Preview Feature)
status: COMPLETED / IMPLEMENTED
ppx_validation: PASS (Technically Sound, Cost-Effective Architecture)
ppx_validation_date: 2026-04-11
---

# ANT-WO-001-v0.4 (Work Order)

> [!IMPORTANT]
> **Lead Developer (Claude Code)**: You are granted "Freedom of Method" within the constraints of this Work Order. Deliver a robust Python map preview script for the Core Engine. 
> Goal: Provide an interactive Web Map view of the satellite imagery (e.g. NDVI layer) without actually attempting to export or store heavy GeoTIFFs.

## 1. Technical Tasks (Scope)

1. **Maintain Original Core Integrity**: 
   - Ensure the existing `async_engine.py` (which exports the CSV) remains completely unmodified and functional. 
   - All extraction and schema definitions for PostGIS (FR-08) remain the primary ingestion method.

2. **Develop Map Preview Generator (`map_previewer.py`)**:
   - Create a new utility script under `03_Build/core_engine/`.
   - The script must import and utilize the existing engine modules (`scene_selector`, `cloud_masking`, `index_calculator`) to obtain the processed Google Earth Engine `Image`.

3. **Tile URL Generation (All Indices)**:
   - Apply visualization parameters for *all* calculated bands (`ndvi`, `evi`, `ndre`, `savi`, `gndvi`).
   - Use `image.getMapId(...)` for each band independently, retrieving 5 distinct Tile URLs (`tile_fetcher.url_format`).

4. **All-in-One HTML Template Construction**:
   - Generate a single standalone `.html` file natively within the Python script using a Leaflet.js web mapping template.
   - Inject *all* Earth Engine Tile URLs into the Leaflet template using a **Layer Control** (`L.control.layers`), allowing the user to toggle between NDVI, EVI, NDRE, SAVI, and GNDVI on the same map.
   - Save the final file to `04_Test/result_output/canopysense_visuals.html` locally.

5. **PostGIS Docker Integration Testing**:
   - Ensure the export stage generates the CSV successfully via `async_engine.py`.
   - The developer must execute the `ingest_to_postgis.py` script locally.
   - Ensure a local `.env` is configured properly targeting the new Docker PostGIS schema we just built (`PGHOST=localhost`, `PGPORT=5432`, `PGDATABASE=canopysense`, `PGUSER=postgres`).
   - Verify the engine successfully bulk-inserts the CSV statistics into the local PostGIS tables.

6. **End-to-End Orchestrator (`engine_launcher.py`)**:
   - Create a master orchestration script named `engine_launcher.py` in the `03_Build/` directory.
   - This script must act as a single-entry bridge to run the entire end-to-end process sequentially:
     1. Run the core CSV extraction export.
     2. Run `map_previewer.py` (generate the HTML visuals).
     3. Run `ingest_to_postgis.py` (inject the data into the local Docker database).

## 2. Success Indicators

- [ ] **No GeoTIFF Code**: Script never attempts an `ee.batch.Export.image.toCloudStorage` avoiding unpredictable raster storage costs.
- [ ] **Standalone Output**: An `.html` file is generated predictably in `04_Test/result_output/` when the script completes.
- [ ] **All-in-One Layer Control**: The rendered HTML contains a UI box to switch between the various vegetation indices (NDVI, EVI, etc.).
- [ ] **Docker PostGIS Inject**: The terminal logs show `ingest_to_postgis.py` successfully committing rows to the `canopysense` Docker database without connection failure or schema mismatches.
- [ ] **One-Click Execution**: Running `python 03_Build/engine_launcher.py` successfully chains the metrics extraction, the HTML map generation, and the PostGIS ingestion seamlessly.

## 3. Implementation Constraints

- **Environment**: Python GEE API (`earthengine-api >= 0.1.418`).
- **Dependencies**: The HTML template must simply use standard CDN calls (e.g., `unpkg.com/leaflet`) to prevent any additional local Python packaging complexities.
- **Security**: Maintain the exact same Service Account credential hooks used elsewhere in the codebase.

## 4. Architectural Risks (PPX-Flagged)

| Risk | Severity | Mitigation |
| :--- | :--- | :--- |
| Expiration of Map IDs | **Low** | GEE `getMapId` tiles expire after 1-2 days. Mitigated: This is intended explicitly as a temporary engineering testing/preview tool, not for permanent backend frontend-hosting right now. |
| Inadvertent cost triggers | **High** | Mitigated: Strict instruction to only use `getMapId()`, no `ee.batch.Export.image` commands allowed. |

---
**ANT (Technical Foreman) Sign-off**: 2026-04-11 (v0.4)
