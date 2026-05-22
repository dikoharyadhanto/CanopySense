---
name: ANT-STR-002-v0.5
project: Canopy Sense
status: COMPLETED / IMPLEMENTED
version: 0.5
---

# ANT-STR-002-v0.5 (Test Plan - Historical Backfill)

## 1. Acceptance Rules

- The script must successfully pull 3 years of imagery and insert it into the `satellite_data` table without failing midway due to external API timeouts.

## 2. Testing Execution (Phases)

### Phase A: Architecture Validation
* **Action:** Review the Python code.
* **Pass Criteria:** The code implements a chronological chunking loop covering exactly 3 years and avoids making a single massive 3-year API query.

### Phase B: Execution Validation
* **Action:** Run `python 03_Build/historical_backfill.py` locally via the terminal.
* **Pass Criteria:**
  1. No memory timeouts from Google Earth Engine.
  2. CSV files sequentially populate the `04_Test/result_output/historical/` folder.
  3. The terminal logs report successful ingestion to PostGIS for every chunk.

### Phase C: PostGIS State Test
* **Action:** Check database totals manually using `SELECT count(*), EXTRACT(year from acquisition_date) FROM canopysense.satellite_data GROUP BY 2;`.
* **Pass Criteria:** The query returns significant row populations across the years 2023, 2024, 2025, and 2026.

## 3. Observations & Output

**(This section to be updated during/after Lead Developer Execution)**

* `[ ]` Code logic chunking validation: pending
* `[ ]` 3-Year script execution complete: pending
* `[ ]` Docker PostGIS DB structural verification: pending

---
**ANT (Technical Foreman) Sign-off**: 2026-04-11 (v0.5)
