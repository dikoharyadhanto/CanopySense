---
name: ANT-STR-001-v0.3
project: Canopy Sense
phase: Tahap I: Ekstraksi Data, Cloud Masking & Rumus Indeks
type: Test Strategy & Report (STR)
ppx_validation: PASS (Structurally Sound, Low-Moderate Risk)
ppx_validation_date: 2026-04-01
---

# ANT-STR-001-v0.3 (Test Plan & Report)

> [!IMPORTANT]
> **QA Controller (Antigravity)**: Use this document to validate the implementation of the Core Engine against the Success Indicators.

> [!NOTE]
> **PPX Validator Verdict**: Structurally sound. Risks low-moderate. Ready for test execution.

## 1. Test Setup

- **Test Data**: Estate polygons (sample set of <2000 polygons).
- **Environment**: Python environment with version-pinned dependencies:
  - `earthengine-api >= 0.1.418`
  - `geopandas >= 0.14`
  - `google-cloud-storage` (for export polling/validation)
- **GEE Assets**: Sentinel-2 (`COPERNICUS/S2_SR_HARMONIZED`), Landsat 8/9 C2 T1_L2.
- **Cloud Score+ Dataset**: `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`
- **Output Destination**: Google Cloud Storage (Bucket: `canopy-sense-data`).

## 2. Test Cases

| ID        | Case                                     | Expected Result                                                                                                                                                                              | Validation Metric                                           | Result      |
|:--------- |:---------------------------------------- |:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |:----------------------------------------------------------- |:----------- |
| **TC-01** | Deterministic Sensor Selection           | If S2 has $\ge 0.6$ valid ratio, select S2 (priority 1). If S2 $\ge 0.2$ but $< 0.6$, select S2 (priority 2). If S2 $< 0.2$ but Landsat $\ge 0.2$, select Landsat. If all $< 0.2$, **SKIP**. | Log selected sensor + valid_pixel_ratio per scene           | [ ] PENDING |
| **TC-02** | Cloud Masking (Cloud Score+ Primary)     | Pixels with `cs_cdf <= 0.60` must be masked (primary). **Secondary safety net**: SCL band (S2) / QA_PIXEL bitwise (Landsat) must be applied after Cloud Score+.                              | Visual inspection + masked pixel count vs total pixel count | [ ] PENDING |
| **TC-03** | Spectral Harmonization (Roy et al. 2016) | Red and NIR bands adjusted using **exact coefficients**. Applied **BEFORE** index calculation.                                                                                               | Compare pre/post harmonized reflectance values              | [ ] PENDING |
| **TC-04** | Index Calculation Accuracy               | NDVI, EVI, SAVI, GNDVI calculated for all sensors. NDRE calculated for S2 only; Landsat `ndre = NULL` explicitly.                                                                            | valid_pixel_ratio stats **per index**                       | [ ] PENDING |
| **TC-05** | Hard Quality Gate                        | If `valid_pixel_ratio < 0.2` per estate geometry, ingestion must be skipped.                                                                                                                 | Verify SKIP event logged + no DB insert                     | [ ] PENDING |
| **TC-06** | Async Retry Logic                        | Simulate a transient GEE export failure; verify script retries up to 3 times with backoff before failing the chunk.                                                                          | Retry count logged per sub-chunk                            | [ ] PENDING |
| **TC-07** | Export Validation & Task Polling (GCS)   | GEE `ee.batch.Export.toCloudStorage` task status must be polled until COMPLETED/FAILED. Validate exported file in GCS bucket `canopy-sense-data`.                                            | Task status log + bucket size/file check                    | [ ] PENDING |
| **TC-08** | DB Schema Alignment [FR-08]              | Exported CSV must match `satellite_data` PostGIS schema: `block_id`, `acquisition_date`, sensor full names, % `cloud_cover`, and `features` JSONB.                                           | Column names, types, and values in CSV match DB DDL exactly | [ ] PENDING |

## 3. Architectural Risks (PPX-Flagged)

| Risk                                                 | Severity | Mitigation                                                                    |
|:---------------------------------------------------- |:-------- |:----------------------------------------------------------------------------- |
| No explicit GEE export task status polling           | Medium   | **TC-07** added. Implement `ee.batch.Export` status polling loop.             |
| Google Drive Service Account Quota                   | **High** | **Mitigated (v0.3)**: Shifted export mechanism to Google Cloud Storage (GCS). |
| Export schema mismatch with PostGIS `satellite_data` | **High** | Resolved via FR-08. TC-08 added to validate all 5 schema corrections.         |

## 4. DB Schema & Architecture Amendment Log

| Date       | Raised By            | Change Summary                                                            |
|:---------- |:-------------------- |:------------------------------------------------------------------------- |
| 2026-04-01 | ANT (schema audit)   | Added TC-08 to validate FR-08 compliance.                                 |
| 2026-04-01 | ANT (execution fail) | Updated TC-07 to reflect pivot from Drive to Google Cloud Storage limits. |

---

**ANT (QA Controller) Sign-off**: 2026-04-01 (v0.3)
**PPX (Validator) Sign-off**: 2026-04-01
