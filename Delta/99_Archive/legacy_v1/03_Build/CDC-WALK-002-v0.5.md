# CDC-WALK-002-v0.5

> [!IMPORTANT]
> **Pre-Implementation Walkthrough** — ANT Approved. Implementation in progress.
> Logic Dependencies: `ANT-WO-002-v0.5` / `ANT-STR-002-v0.5`

---

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 002 |
| **Document Type** | Technical Walkthrough (WALK) |
| **Version** | v0.5 |
| **Status** | ANT Approved — Implementation In Progress |
| **Lead Developer** | Claude Code (CDC) |
| **Work Order Ref** | `ANT-WO-002-v0.5` |
| **Test Plan Ref** | `ANT-STR-002-v0.5` |

---

## 2. Task Interpretation

Build `03_Build/historical_backfill.py` — a standalone script that seeds
`canopysense.satellite_data` with 3 years of historical satellite imagery
statistics (April 2023 → April 2026) using 7-day time chunks identical to
the live autoscheduler window.

**Approved design (Option A — revised to weekly):**
One best scene per 7-day chunk. Scene selection uses the existing
`select_best_scene()` priority logic (S2 Tier 1 → S2 Tier 2 → Landsat → Skip).
Blocks that fail the FR-03 cloud gate for that scene remain blank for that week.

**Rationale for weekly (not monthly) chunks:**
The live engine runs every 7 days, producing up to 4 observations per block
per month. Monthly chunks in the backfill would produce only 1 observation per
month — a 4× frequency mismatch that breaks STL seasonal decomposition. Weekly
7-day windows ensure historical and live data share identical temporal sampling.

---

## 3. Proposed Approach

### Execution Flow

```
Load blocks from canopysense.blocks (same as engine_launcher)
Initialize GEE
Build AOI from block union

For each 7-day window in [Apr 2023 → Apr 2026] (~156 weeks):
  date_start = current window start
  date_end   = date_start + 6 days (or period end if shorter)

  log "Week {N}/{total}: {DD Mon YYYY} → {DD Mon YYYY}"

  select_best_scene(aoi_ee, date_start, date_end)
    → skip=True : log "No valid scene for this week — skipping." → continue
    → found     :
        apply_cloud_mask(image, sensor)
        prepare_image(image, sensor)
        calculate_indices(image, sensor)
        actual_date = image.date().format("YYYY-MM-dd").getInfo()
        _extract_to_csv(image, blocks_gdf, sensor, actual_date, low_quality)
          → write CSV: 04_Test/result_output/historical/canopysense_{actual_date}.csv
        run_ingestion(input_dir=historical_output_dir)
          → ON CONFLICT (block_id, acquisition_date, sensor) DO NOTHING
        log "Week done — {N} rows inserted."

log "Backfill complete."
```

### Weekly Chunking

7-day windows matching the live engine exactly:
- Week 1:  `2023-04-01` → `2023-04-07`
- Week 2:  `2023-04-08` → `2023-04-14`
- ...
- ~Week 156: `2026-04-24` → `2026-04-30`

Total windows: ~156 (exact count depends on end month boundary).

Month end dates computed with `calendar.monthrange()` — handles leap years correctly.

### Restart Safety & Resume System

Three-layer guard makes reruns fast and API-efficient:

| Layer | Guard | Action on hit |
| :--- | :--- | :--- |
| 1 | `satellite_data` has rows for this window | Skip — no GEE call |
| 2 | Window in `backfill_skipped` (backlog) | Skip — no GEE call |
| 3 | GEE returns no scene or all blocks fail FR-03 | Write to backlog, continue |

`canopysense.backfill_skipped` schema:
```sql
(id SERIAL PK, window_start DATE, window_end DATE,
 skip_reason TEXT,   -- 'no_scene' | 'fr03_all_failed'
 skipped_at TIMESTAMPTZ,
 UNIQUE (window_start, window_end))
```

- `ON CONFLICT DO NOTHING` in PostGIS prevents duplicate satellite_data rows.
- CSV files accumulate in `historical/` — existing files overwritten safely.
- Backlog ensures permanently clouded windows are never retried, preserving GEE quota.

---

## 4. Files to Create / Modify

| File | Action | Purpose |
| :--- | :--- | :--- |
| `03_Build/historical_backfill.py` | **NEW** | Historical backfill script — 36-month loop |
| `04_Test/result_output/historical/` | **CREATE DIR** | Output directory for historical CSVs |
| All `core_engine/*` modules | **ZERO CHANGE** | Reused as-is |
| `03_Build/ingestion/ingest_to_postgis.py` | **ZERO CHANGE** | Reused as-is |

---

## 5. Dependencies

No new packages. All required packages already in `requirements.txt`:
`earthengine-api`, `geopandas`, `pandas`, `psycopg2-binary`, `python-dotenv`

`calendar` module used for month-end date calculation — Python stdlib, no install needed.

---

## 6. Flags / Risks

| Flag | Severity | Status |
| :--- | :--- | :--- |
| Option A (one scene per 7-day window) | — | ✅ ANT Approved |
| FR-03 blanks are expected | Low | Accepted by design — tropical cloud cover causes sparse weeks |
| GEE runtime ~156 sequential API calls | Medium | ~60–90 min estimated; acceptable for one-time backfill |
| Same actual_date across adjacent windows | Low | ON CONFLICT handles deduplication gracefully |
| `ingest_to_postgis` reads ALL CSVs in dir | Medium | Script points to `historical/` subdirectory, isolated from weekly CSVs |
| Monthly → Weekly design change | Low | Corrected before execution; WALK/IMPL docs updated to reflect weekly design |
