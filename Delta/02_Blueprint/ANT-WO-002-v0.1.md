# ANT-WO-002-v0.1 — Work Order

> [!IMPORTANT]
> **Dependencies**: `GMN-STRAT-001-v1.0`. **Migrated from legacy** `ANT-WO-002-v0.5`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Work Order (WO) |
| **Version** | v0.1 |
| **Status** | COMPLETE |
| **Legacy Source** | ANT-WO-002-v0.5 (2026-04-11) |
| **PPX Validation** | PASS |

## 2. Scope — Historical Backfill

Create a script to loop backward 3 years (April 2023 → April 2026) extracting historical vegetation indices from Sentinel-2 and Landsat, seeding the `satellite_data` table for trend analysis and STL decomposition.

### 2.1 Technical Tasks

1. **Develop `historical_backfill.py`** in `03_Build/`
2. Loop backward in 7-day weekly chunks (matching live engine cadence)
3. Process both Sentinel-2 and Landsat data
4. Output CSV logs to `04_Test/result_output/historical/`
5. Insert into PostGIS `satellite_data` using existing `ON CONFLICT DO NOTHING`

### 2.2 Success Indicators

- 161 weekly chunks processed without GEE timeouts
- Terminal logs report successful batch inserts to PostGIS
- No duplicate errors from overlapping dates
- CSV backups organized in `historical/` directory

### 2.3 Key Design Decisions

| Decision | Rationale |
| :--- | :--- |
| Weekly 7-day chunks (not monthly) | Matches live engine cadence; monthly would produce 1 obs/month vs 4 obs/month live, breaking STL seasonal decomposition |
| `backfill_skipped` backlog table | Prevents GEE API quota waste on reruns — permanently clouded windows recorded once, skipped forever |
| Three-layer resume guard | Layer 1: has-data check → Layer 2: backlog check → Layer 3: GEE call + backlog write on failure. Reruns near-instant. |

## 3. Files Created

| Path | Action |
| :--- | :--- |
| `03_Build/historical_backfill.py` | New |
| `04_Test/result_output/historical/` | Created |
| `canopysense.backfill_skipped` (PostGIS) | New table |
| All `core_engine/*` + `ingest_to_postgis.py` | Zero change (reused as-is) |

---

*Migrated from legacy `ANT-WO-002-v0.5`. See `CDC-IMPL-002-v0.1` for full detail.*
