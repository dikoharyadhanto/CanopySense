# CDC-WALK-001-v0.1
> [!IMPORTANT]
> **Logic Dependencies**: Requires `CDC-IMPL` + `ANT-STR`.

## 0. Pre-Implementation Plan (Submit to ANT BEFORE coding)

> **ANT Approval Status:** `[x] Approved` — 2026-04-01

| Item | Detail |
| :--- | :--- |
| **Task Interpretation** | Build a Python GEE Core Engine module covering: (1) EE init with Service Account, (2) deterministic 7-day sensor selection (S2 priority → Landsat → skip), (3) Cloud Score+ primary masking (`cs_cdf > 0.60` = KEEP) + SCL/QA_PIXEL secondary, (4) Roy et al. 2016 Red/NIR harmonization before index calc, (5) NDVI/EVI/SAVI/GNDVI/NDRE (NDRE S2-only, NULL for Landsat), (6) hard quality gate `valid_pixel_ratio >= 0.2`, (7) async export in 2,000-poly sub-chunks with 3x exponential backoff retry. |
| **Proposed Approach** | Modular Python package (one file per concern). Server-side GEE operations throughout. Scene selection via `filterDate().filterBounds()` + priority tier logic. Cloud Score+ join by `system:time`. Harmonization via `.expression()` before indices. Quality gate via `reduceRegion(ee.Reducer.mean())` on mask band. Async engine sub-chunks input GDF, submits `ee.batch.Export.table.toDrive()`, polls `task.status()`, retries with `2^attempt * base_wait` backoff. Credentials loaded from `EE_SERVICE_ACCOUNT_KEY` env var only. |
| **Files to Create/Modify** | `03_Build/core_engine/__init__.py`, `ee_init.py`, `scene_selector.py`, `cloud_masking.py`, `harmonization.py`, `index_calculator.py`, `quality_gate.py`, `async_engine.py`; `03_Build/requirements.txt`; `03_Build/CDC-IMPL-001-v0.1.md`; `03_Build/CDC-WALK-001-v0.1.md` |
| **Dependencies** | `earthengine-api>=0.1.418`, `geopandas>=0.14`, `pandas>=2.0` |
| **Flags / Risks** | (1) `valid_pixel_ratio` computed as mask-band mean via `reduceRegion` — confirm if alternative method expected. (2) Cloud Score+ only for S2; Landsat uses QA_PIXEL only. (3) NDRE uses S2 B5 (~705nm). (4) Export as FeatureCollection (mean index per estate polygon via `reduceRegion`) — confirm if per-pixel raster export is intended instead. |

> **ANT must approve this section before implementation begins (Sections 1–5).**

---

## 1. Metadata
| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Implementation Walkthrough (WALK) |
| **Version** | v0.1 |
| **Status** | Finalized |
| **Lead Developer** | Claude Code (CDC) |
| **Work Order Ref** | `ANT-WO-001-v0.2` |
| **Test Plan Ref** | `ANT-STR-001-v0.2` |

---

## 2. Feature Demonstration

> **Summary of Work:** Delivered a fully modular `core_engine` Python package implementing all 7 FR items from ANT-WO-001-v0.1. The package covers GEE initialization with Service Account support, deterministic 7-day sensor selection (S2 tier 1/2 → Landsat tier 3 → skip), Cloud Score+ primary + SCL/QA_PIXEL secondary dual masking, Roy et al. (2016) Red/NIR harmonization before index calculation, NDVI/EVI/SAVI/GNDVI/NDRE index calculation, hard quality gate (valid_pixel_ratio ≥ 0.2 per estate), and async export in 2,000-polygon sub-chunks with 3× exponential backoff retry. FR-07 low_quality flag for Landsat scenes with 0.2 ≤ ratio < 0.6 is implemented at scene level.

### Verification Proofs:
[Awaiting QA execution by ANT / Gemini-based agents against ANT-STR-001-v0.1]

---

## 3. Test Verification Results (STR Checklist)
| Scenario ID | Status | Notes |
| :--- | :--- | :--- |
| **TC-01** | [ ] PENDING | Deterministic Sensor Selection |
| **TC-02** | [ ] PENDING | Cloud Masking (Cloud Score+ Primary + Secondary) |
| **TC-03** | [ ] PENDING | Spectral Harmonization (Roy et al. 2016) |
| **TC-04** | [ ] PENDING | Index Calculation Accuracy |
| **TC-05** | [ ] PENDING | Hard Quality Gate |
| **TC-06** | [ ] PENDING | Async Retry Logic |
| **TC-07** | [ ] PENDING | Export Validation & Task Polling |

---

## 4. Final Root-Cause Analysis (RCA)
> [Pending — to be filled after implementation]

---

## 5. Residual Risks & Next Steps
* **Risks:** [Pending]
* **Next Steps:** [Pending]

---

## 6. Handoff Signal to ANT

> **Status:** `READY FOR QA`
> **IMPL Log:** `CDC-IMPL-001-v0.1.md`

| STR Scenario | Result |
| :--- | :--- |
| All TC-01 through TC-08 from `ANT-STR-001-v0.2` | `[ ] AWAITING QA EXECUTION` |
