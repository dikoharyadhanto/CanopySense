---
name: ANT-STR-001-v0.4
project: Canopy Sense
phase: Tahap I: Ekstraksi Data (Map Preview Feature)
status: COMPLETED / IMPLEMENTED
---

# ANT-STR-001-v0.4 (Test Plan)

> [!NOTE]
> This Support Test Report (STR) complements Work Order `ANT-WO-001-v0.4` to validate the HTML Map Preview generator.

## 1. Context & Objective
Confirm that the Lead Developer has successfully built a lightweight viewer generator that proves Earth Engine visualizations operate flawlessly, totally side-stepping the costly GeoTIFF download process.

## 2. Test Plan (Automated / Manual)

### Phase A: Architecture Validation
* **Action:** Check `03_Build/core_engine/map_previewer.py` codebase.
* **Pass Criteria:**
  1. No `ee.batch.Export.image` functions are present.
  2. The code actively calls `getMapId()` and successfully constructs an HTML string wrapping the Leaflet.js libraries via CDN.

### Phase B: Execution Validation
* **Action:** Run the master orchestrator locally via the terminal from the project root: `python 03_Build/engine_launcher.py`.
* **Pass Criteria:**
  1. Console successfully reports initialization via Service Account.
  2. The script chains the CSV extraction, the Map preview, and the PostGIS injection workflows sequentially.
  3. The file `04_Test/result_output/canopysense_visuals.html` appears without errors.

### Phase C: Visual Acceptance Test (UAT)
* **Action:** The Director (User) physically opens `04_Test/result_output/canopysense_visuals.html` using a Web Browser.
* **Pass Criteria:**
  1. A world map widget correctly loads on the screen.
  2. The map features a Layer Control menu in the corner. You can click and instantly switch the map visuals between NDVI, EVI, NDRE, SAVI, and GNDVI perfectly rendered.

### Phase D: PostGIS Integration Test
* **Action:** Execute the ingestion script to inject CSV tables into the Docker DB: `python 03_Build/ingestion/ingest_to_postgis.py`.
* **Pass Criteria:**
  1. No connection errors or credential rejections from the Docker container.
  2. Terminal explicitly reports `Committed X row(s) to satellite_data`.
  3. No schema/column mismatch errors from PostGIS.

## 3. Observations & Output

**(This section to be updated during/after Lead Developer Execution)**

* `[ ]` Code logic check (Engine Launcher & Previewer): pending
* `[ ]` Master Script execution completion: pending
* `[ ]` HTML Map Viewer generation: pending
* `[ ]` Visual Layer Toggle check: pending
* `[ ]` Docker PostGIS DB insertion: pending

---
**ANT (Technical Foreman) Sign-off**: 2026-04-11 (v0.4)
