# CDC-IMPL-002-v0.5

> [!IMPORTANT]
> **Logic Dependencies**: `ANT-WO-002-v0.5` / `ANT-STR-002-v0.5`

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 002 |
| **Document Type** | Implementation Log (IMPL) |
| **Version** | v0.5 |
| **Status** | Complete |
| **Lead Developer** | Claude Code (CDC) |
| **Work Order Ref** | `ANT-WO-002-v0.5` |
| **Test Plan Ref** | `ANT-STR-002-v0.5` |

---

## 1b. Environment & Stack

| Field | Value |
| :--- | :--- |
| **OS / Platform** | Any (no OS-specific code) |
| **Runtime / Language** | Python 3.10+ |
| **Key Libraries** | `earthengine-api>=0.1.418`, `geopandas>=0.14`, `pandas>=2.0`, `psycopg2-binary>=2.9`, `python-dotenv>=1.0`, `calendar` (stdlib) |
| **GEE Export** | Synchronous `reduceRegions().getInfo()` — no GCS |
| **Date Range** | April 2023 → April 2026 (161 weekly 7-day chunks) |

---

## 2. Technical Decision Log

| Decision | Rationale |
| :--- | :--- |
| Weekly 7-day chunks (not monthly) | Live engine runs every 7 days — monthly chunks produce 1 obs/month historically vs ~4 obs/month live, breaking STL seasonal decomposition. Caught and corrected before first run. |
| `backfill_skipped` backlog table | Prevents GEE API quota waste on reruns. Windows permanently clouded out (no scene / all blocks fail FR-03) are recorded once and skipped forever. |
| Three-layer resume guard | Layer 1 (has-data check) → Layer 2 (backlog check) → Layer 3 (GEE call + backlog write on failure). Makes reruns near-instant for already-processed history. |
| Single DB connection held open for full run | Backlog reads/writes require DB access inside the main loop. Connection opened before loop, closed in `finally` block. |

---

## 3. Files Created / Modified

| File Path | Action | Purpose |
| :--- | :--- | :--- |
| `03_Build/historical_backfill.py` | **NEW** | 161-week historical backfill loop with resume/backlog system |
| `04_Test/result_output/historical/` | **CREATED** | Isolated output dir for historical CSVs |
| `canopysense.backfill_skipped` (PostGIS table) | **NEW** | Permanent skip registry — prevents GEE quota waste on reruns |
| All `core_engine/*` + `ingest_to_postgis.py` | **ZERO CHANGE** | Reused as-is per WO constraint |

---

## 4. Key Logic

```
_ensure_backlog_table(conn)          # CREATE TABLE IF NOT EXISTS backfill_skipped

_generate_weekly_chunks(start="2023-04", end="2026-04")
  → 161 tuples of (date_start, date_end, label) at 7-day intervals

for each week:
  [Layer 1] _has_existing_data(conn, date_start, date_end)
    → True  : "Already in DB — resuming past this week."  → continue (no GEE call)

  [Layer 2] _is_in_backlog(conn, date_start, date_end)
    → True  : "In backlog (permanent skip)."             → continue (no GEE call)

  [Layer 3] select_best_scene(aoi_ee, date_start, date_end) → SceneResult
    → skip=True  : _write_to_backlog(reason="no_scene")        → continue
    → found      :
        cloud_mask → harmonize → indices
        actual_date from image.date().getInfo()
        _extract_to_csv() → historical/{actual_date}.csv
        → n_passed == 0 : _write_to_backlog(reason="fr03_all_failed") → continue
        run_ingestion(historical_dir) → PostGIS

Design note: Weekly (not monthly) to match live engine's 7-day search window.
Monthly was rejected — frequency mismatch breaks STL seasonal decomposition.
```

---

## 5. Dependency Changes

None — all packages already present in `requirements.txt`.

---

## 6. STR Test Checklist

| Test (from ANT-STR-002-v0.5) | Status |
| :--- | :--- |
| Phase A: Chunking loop covers 161 weeks at 7-day intervals, no single 3-year query | ✅ Pass |
| Phase B: No GEE memory timeouts | ✅ Pass |
| Phase B: CSVs populate `04_Test/result_output/historical/` | ✅ Pass — 84 CSV files written |
| Phase B: Terminal logs report ingestion per chunk | ✅ Pass |
| Phase C: `SELECT count(*) GROUP BY year` returns data across 2023–2026 | ✅ Pass |
| Post-WO: Resume system — Layer 1 has-data check skips DB-present windows | ✅ Verified |
| Post-WO: Resume system — Layer 2 backlog check skips with no GEE call | ✅ Verified |
| Post-WO: Backlog table populated with 77 known-bad windows (65 no_scene + 12 fr03_all_failed) | ✅ Done |

---

## 7. Execution Results

### Run Summary (2026-04-11)

| Metric | Value |
| :--- | :--- |
| Total weekly windows | 161 |
| Weeks with valid scene | 96 |
| Weeks no valid scene (cloud/gap) | 65 |
| Weeks with data (passed FR-03) | 84 |
| Total rows inserted to PostGIS | 1,784 |
| Runtime | ~8 minutes |
| Errors | 0 |

### PostGIS State (Phase C)

```sql
SELECT EXTRACT(year FROM acquisition_date) AS year, count(*) AS rows
FROM canopysense.satellite_data GROUP BY 1 ORDER BY 1;
```

| Year | Rows |
| :--- | :--- |
| 2023 | 814 |
| 2024 | 732 |
| 2025 | 651 |
| 2026 | 127 |
| **Total** | **2,324** |

### Observations

- 40% of weekly windows returned no valid scene (cloud cover in tropical area — expected).
- Dense observation clusters in Apr–Nov (drier months); sparser in Dec–Feb (wet season).
- 2026 row count lower as only Jan–Apr covered (partial year) and heavy cloud in Jan–Feb.
- ON CONFLICT DO NOTHING handled all re-run safety correctly — 0 duplicate errors.
- `ingest_to_postgis` cumulative CSV re-read per chunk is functionally correct (conflict-safe) but creates O(n²) file reads. Acceptable for one-time backfill; not relevant to live engine.

### Backlog State (Post-Run)

| skip_reason | count |
| :--- | :--- |
| no_scene | 65 |
| fr03_all_failed | 12 |
| **Total** | **77** |

All 77 windows back-populated from run log. Future reruns skip these instantly (no GEE call).

### Resume System Spot-Check (April 2023, re-run)

```
Week 1/5: 01 Apr 2023 → 07 Apr 2023  → Already in DB — resuming
Week 2/5: 08 Apr 2023 → 14 Apr 2023  → Already in DB — resuming
Week 3/5: 15 Apr 2023 → 21 Apr 2023  → In backlog (permanent skip)
Week 4/5: 22 Apr 2023 → 28 Apr 2023  → In backlog (permanent skip)
Week 5/5: 29 Apr 2023 → 30 Apr 2023  → GEE called → no scene → written to backlog
```

Confirmed: only 1 GEE call made for 5 windows. Resume layers working correctly.
