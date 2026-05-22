---
name: ANT-WO-001-v0.3
project: Canopy Sense
phase: Tahap I: Ekstraksi Data, Cloud Masking & Rumus Indeks
status: ACTIVE
ppx_validation: PASS (Technically Sound, Source-Aligned)
ppx_validation_date: 2026-04-01
---

# ANT-WO-001-v0.3 (Work Order)

> [!IMPORTANT]
> **Lead Developer (Claude Code)**: You are granted "Freedom of Method" within the constraints of this Work Order. Deliver a robust GEE Python module for the Core Engine. This version pivots the export mechanism from Google Drive to Google Cloud Storage (GCS).

> [!NOTE]
> **PPX Validator Verdict**: Technically sound, source-aligned. Freedom of Method viable within constraints.

## 1. Technical Tasks (Scope)

1.  **GEE Initialization**: Implement standard EE initialization with Service Account support (refer to `05_Reference/004 SWM_Apps/scripts/gee_hooks.py` for pattern).
2.  **Deterministic Scene Selection [FR-01]**:
    -   Window: 7 days.
    -   Priority:
        1.  Sentinel-2 (ratio $\ge 0.6$)
        2.  Sentinel-2 (ratio $\ge 0.2$)
        3.  Landsat 8/9 (ratio $\ge 0.2$)
    -   Action: Skip ingestion if all $< 0.2$.
3.  **Cloud Masking [FR-02]**:
    -   Implement **Cloud Score+** as primary filter.
    -   **Dataset**: `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`
    -   **Polarity Clarification**: `cs_cdf` represents the probability a pixel is **CLEAR**. Therefore:
        -   **KEEP** (unmask) pixels where `cs_cdf > 0.60` (≥60% probability of clear sky).
        -   **MASK** (discard) pixels where `cs_cdf <= 0.60` (likely cloudy).
    -   **Secondary Safety Net**: Apply SCL band (S2) or QA_PIXEL bitwise (Landsat) after Cloud Score+ to catch residual cloud/shadow.
4.  **Spectral Harmonization [FR-04]**:
    -   Apply Roy et al. (2016) coefficients to **Red** and **NIR** reflectance bands only.
    -   **Exact Coefficients (Landsat 8 → Sentinel-2)**:
        -   Red: `slope = 1.0536`, `intercept = -0.0049`
        -   NIR: `slope = 1.0740`, `intercept = -0.0102`
        -   Ensure this happens **BEFORE** index calculation.
        -   Cite coefficients in code comments for traceability.
5.  **Index Calculation [FR-05]**:
    -   Calculate: NDVI, EVI, SAVI, GNDVI for all sensors.
    -   Calculate: NDRE for Sentinel-2 only (Red Edge B5); mark as `NULL` for Landsat.
6.  **Hard Quality Gate [FR-03]**:
    -   Validate `valid_pixel_ratio >= 0.2` per estate geometry.
7.  **Async Engine [FR-06]**:
    -   Implement sub-chunking (2,000 polygons per export).
    -   **Use `ee.batch.Export.table.toCloudStorage()`** (Changed from `toDrive` due to Service Account quota limitations).
    -   Target Bucket: `canopy-sense-data`.
    -   Implement **Retry Logic (3x)** with **exponential backoff** for failed tasks.
    -   Poll `ee.batch.Export` task status until `COMPLETED` or `FAILED`.
    -   Target GEE-specific errors: `quotaExceeded`, `computeTimeout`, transient network failures.
8.  **DB Schema Alignment [FR-08]**:
    -   The export CSV must align exactly with the `satellite_data` table in PostGIS.
    -   **Identifier**: Use `block_id` (INTEGER — FK to `blocks.id`).
    -   **Date column**: `acquisition_date`.
    -   **Sensor name normalization**: `sentinel-2`, `landsat-8`, `landsat-9`.
    -   **cloud_cover**: `(1 - valid_pixel_ratio) * 100` as `NUMERIC(5,2)`.
    -   **features JSONB**: Package `valid_pixel_ratio` (float) and `low_quality` (boolean).
    -   **Final export column order**: `block_id`, `acquisition_date`, `sensor`, `cloud_cover`, `ndvi`, `evi`, `ndre`, `savi`, `gndvi`, `features`.

## 2. Success Indicators

-   [ ] **Correct Selection**: Script correctly picks S2 over Landsat if both are available and S2 meets the threshold.
-   [ ] **Masking Precision**: Cloud pixels are effectively masked (discarded) where `cs_cdf <= 0.60`. SCL/QA_PIXEL secondary filter catches residuals.
-   [ ] **Harmonization Validity**: Data from S2 and Landsat shows spectral consistency post-harmonization using exact Roy coefficients.
-   [ ] **NDRE Handling**: Landsat records explicitly state `ndre = NULL`.
-   [ ] **Retry Resilience**: Async tasks successfully retry (with exponential backoff) on transient EE failures up to 3 times.
-   [ ] **Export Integrity**: Exported files to GCS are validated post-download (row count / file size check).
-   [ ] **DB Schema Match [FR-08]**: Exported CSV columns match `satellite_data` table exactly.

## 3. Implementation Constraints

-   **Environment**: Python GEE API (`earthengine-api >= 0.1.418`).
-   **No Carry-Forward**: If no valid data, report "No Reliable Data". Do not repeat previous week's data.
-   **Security**: Use Service Account credentials. **No hard-coded credentials**.

## 4. Architectural Risks (PPX-Flagged)

| Risk | Severity | Mitigation |
| :--- | :--- | :--- |
| `cs_cdf` polarity confusion | **High** | Clarification added in FR-02: KEEP `> 0.60`, MASK `<= 0.60`. |
| Google Drive Service Account Quota | **High** | **Mitigated**: Shifted export mechanism to Google Cloud Storage (GCS). |
| Export schema mismatch with PostGIS | **High** | Resolved via FR-08 amendment. |

## 5. References

-   PRD: `00_Strategy/GMN-PRD-000-v0.3.md`
-   Logic Flow: `00_Strategy/GMN-FLOW-001-v0.3.md`
-   Reference Code: `05_Reference/004 SWM_Apps/scripts/gee_hooks.py`

## 6. DB Schema & Architecture Amendment Log

| Date | Raised By | Change Summary |
| :--- | :--- | :--- |
| 2026-04-01 | ANT (schema audit) | Added FR-08: 5 export schema mismatches corrected to align with PostGIS `satellite_data`. |
| 2026-04-01 | ANT (execution fail) | Pivoted export from Google Drive to Google Cloud Storage (`toCloudStorage`) to bypass Service Account Drive quota restrictions. |

---
**ANT (Technical Foreman) Sign-off**: 2026-04-01 (v0.3)
**PPX (Validator) Sign-off**: 2026-04-01
