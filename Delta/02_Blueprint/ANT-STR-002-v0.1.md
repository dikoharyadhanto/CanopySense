# ANT-STR-002-v0.1 — Test Plan (STR)

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-002-v0.1`. **Migrated from legacy** `ANT-STR-002-v0.5`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Test Plan (STR) |
| **Version** | v0.1 |
| **Status** | COMPLETE |

## 2. Test Phases

| Phase | Action | Pass Criteria | Result |
| :--- | :--- | :--- | :---: |
| A | Code review — chunking loop | Covers exactly 3 years in 7-day increments; no massive single query | ✅ |
| B | Run `python 03_Build/historical_backfill.py` | No GEE timeouts; CSVs populate `historical/`; PostGIS ingestion logged per chunk | ✅ |
| C | PostGIS verification — `SELECT count(*), EXTRACT(year...)` | Row populations across 2023, 2024, 2025, 2026 | ✅ |

## 3. Execution Results

- **161 weekly chunks** processed (April 2023 → April 2026)
- Chunking logic: 7-day windows, matching live engine cadence
- `backfill_skipped` backlog table prevents GEE quota waste on reruns
- All phases PASSED

---

*Migrated from legacy `ANT-STR-002-v0.5`.*
