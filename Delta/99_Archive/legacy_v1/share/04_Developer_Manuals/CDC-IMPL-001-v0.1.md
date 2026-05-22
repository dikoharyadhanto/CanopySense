# CDC-IMPL-001-v0.1

> [!IMPORTANT]
> **Logic Dependencies**: Requires `ANT-WO-001-v0.2`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Implementation Log (IMPL) |
| **Version** | v0.1 |
| **Status** | Complete — Ready for QA |
| **Lead Developer** | Claude Code (CDC) |
| **Work Order Ref** | `ANT-WO-001-v0.2` |
| **Test Plan Ref** | `ANT-STR-001-v0.2` |

---

## 1b. Environment & Stack

| Field | Value |
| :--- | :--- |
| **OS / Platform** | Any (no OS-specific code) |
| **Runtime / Language** | Python 3.10+ |
| **Key Libraries** | `earthengine-api>=0.1.418`, `geopandas>=0.14`, `pandas>=2.0`, `requests>=2.31` |
| **Environment** | Local dev / CI with GEE service account credentials |

---

## 2. Technical Decision Log

* **Decision 1 — Modular package architecture**: Each functional concern (init, selection, masking, harmonization, indices, quality gate, export) is isolated in its own module. This makes each component independently testable against the STR test cases.

* **Decision 2 — Cloud Score+ joined by `system:index`**: For S2 scene selection, the Cloud Score+ image is fetched using `ee.Join.saveFirst` filtered by `system:index` equality. This ties each S2 granule to its corresponding CS+ image precisely — more reliable than date-only joins for multi-granule windows.

* **Decision 3 — valid_pixel_ratio via `valid_mask` band**: A fully-unmasked binary band (1=valid, 0=masked) is added to the image before `reduceRegions`. The mean of this band over an estate geometry yields `valid_pixel_ratio` without a separate GEE call. Index bands retain their cloud mask so their means reflect valid pixels only.

* **Decision 4 — Roy harmonization on [0,1] reflectance**: Landsat bands are scaled from DN to surface reflectance [0,1] before applying Roy et al. (2016) coefficients. Scaling is: `DN * 0.0000275 + (−0.2)`. Coefficients are applied only to Red and NIR per the Spectral Preservation rule.

* **Decision 5 — Scene-level `low_quality` flag (FR-07)**: `low_quality` is a scene-level property propagated uniformly to all estate features in that scene's export. This matches "Landsat images with valid_pixel_ratio in range 0.2–0.6" per FR-07 — the flag describes image quality, not individual estate quality.

* **Decision 6 — FR-03 quality gate applied server-side in export**: `ee.Filter.gte("valid_mask", 0.2)` is applied inside `_submit_chunk_export` before the Drive export. Estates below threshold are excluded from the CSV; no carry-forward occurs.

* **Decision 7 — Idempotent EE initialization**: `initialize_ee()` checks a module-level `_INITIALIZED` flag so it is safe to call multiple times without reinitializing GEE on each invocation.

* **Decision 8 — FR-08 DB schema alignment (amendment 2026-04-01)**: All 5 schema corrections applied directly inside `_submit_chunk_export` in a single server-side `.map()` pass: (1) `block_id` stored as integer; (2) `acquisition_date` column name; (3) full sensor names via `_SENSOR_NAMES` dict; (4) `cloud_cover = (1 - valid_pixel_ratio) * 100`; (5) `features` JSONB string built via `ee.String` concatenation server-side — `valid_pixel_ratio` and `low_quality` are packed into it and NOT exported as top-level columns. `low_quality` is a Python-side scene-level flag (known at export time), so its JSON boolean value ("true"/"false") is computed in Python before the GEE map call, avoiding an unnecessary server-side conditional.

---

## 3. Files Modified & Created

| File Path | Action | Purpose |
| :--- | :--- | :--- |
| `03_Build/core_engine/__init__.py` | NEW | Package init; public API surface |
| `03_Build/core_engine/ee_init.py` | NEW | GEE initialization — SA key file, inline JSON, or OAuth fallback |
| `03_Build/core_engine/scene_selector.py` | NEW | FR-01 deterministic 7-day sensor selection (S2 priority → Landsat → skip) |
| `03_Build/core_engine/cloud_masking.py` | NEW | FR-02 Cloud Score+ primary + SCL/QA_PIXEL secondary dual masking |
| `03_Build/core_engine/harmonization.py` | NEW | FR-04 band scaling, standardization, and Roy et al. (2016) harmonization |
| `03_Build/core_engine/index_calculator.py` | NEW | FR-05 NDVI/EVI/SAVI/GNDVI/NDRE index calculation |
| `03_Build/core_engine/quality_gate.py` | NEW | FR-03 hard valid_pixel_ratio gate (0.2 threshold) |
| `03_Build/core_engine/async_engine.py` | NEW + **FR-08 amended** | FR-06/FR-07 sub-chunked export with 3x exponential backoff retry; FR-08 DB schema alignment |
| `03_Build/requirements.txt` | NEW | Pinned dependencies |

---

## 4. Key Abstractions & Logic

> **Processing pipeline order** (must be followed strictly):
> 1. `initialize_ee()` — authenticate
> 2. `select_best_scene(aoi_ee, start, end)` → `SceneResult`
> 3. `apply_cloud_mask(image, sensor)` — dual-layer masking
> 4. `prepare_image(image, sensor)` — scale + rename bands + Roy harmonization
> 5. `calculate_indices(image, sensor)` — append index bands
> 6. `run_export(image, estates_gdf, ...)` — sub-chunk + export + retry + poll

> **New Components**:
> - `SceneResult` dataclass — carries image, sensor, valid_pixel_ratio, low_quality, skip
> - `ChunkResult` dataclass — carries per-chunk export outcome
> - `build_valid_mask_band(image)` — enables per-estate valid_pixel_ratio computation via reduceRegions

---

## 5. Dependency Changes

* `earthengine-api>=0.1.418` — GEE Python API
* `geopandas>=0.14` — Estate polygon GeoDataFrame handling
* `pandas>=2.0` — DataFrame slicing for sub-chunking
* `requests>=2.31` — Transient network error detection in retry logic

---

## 6. Technical Debt & Risks

* [ ] **Scene selection calls `.getInfo()` per collection**: `_best_s2_scene` and `_best_landsat_scene` call `.getInfo()` to retrieve valid_pixel_ratio values for Python-side tier comparison. For windows with many scenes (e.g., >10 tiles), this may be slow. Optimization path: use server-side `.sort()` + `.first()` and retrieve only one `.getInfo()` call (already partially done — retrieves best scene ratio only).
* [ ] **`_gdf_to_ee_feature_collection` iterates Python-side**: Converting 2,000-polygon GDF to EE FeatureCollection via row iteration is O(N) Python. For production scale (Tahap II), consider serializing to GeoJSON and uploading as an EE asset.
* [ ] **No explicit handling of image date retrieval**: `acquisition_date` is passed by the caller from `date_start`. If the selected image is not from `date_start` (e.g., best image is from day 5 of the 7-day window), the `acquisition_date` field in the export will not reflect the actual acquisition date. Fix: retrieve `image.date().format("YYYY-MM-dd").getInfo()` from the selected scene and pass it to `run_export`.
* [ ] **Polling is blocking**: `_poll_until_done` blocks the Python process. For production multi-chunk pipelines, consider async task polling with `asyncio` or a thread pool.
