# CDC-IMPL-002-v0.1 — Implementation Log

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-002-v0.1`. **Migrated from legacy** `CDC-IMPL-002-v0.5`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Implementation Log (IMPL) |
| **Version** | v0.1 |
| **Status** | COMPLETE |

## 2. Technical Decisions

| # | Decision | Rationale |
| :--- | :--- | :--- |
| 1 | Weekly 7-day chunks | Matches live engine cadence; monthly would produce only 1 obs/month vs 4 obs/month live, breaking STL |
| 2 | `backfill_skipped` backlog table | Windows permanently clouded out are recorded once and skipped forever; prevents GEE API quota waste |
| 3 | Three-layer resume guard | Layer 1 (has-data check) → Layer 2 (backlog check) → Layer 3 (GEE + backlog write on failure) |
| 4 | Single DB connection held for full run | Backlog reads/writes require DB inside loop |

## 3. Execution Flow

```
generate weekly chunks (161 × 7-day windows, Apr 2023 → Apr 2026)

for each week:
  [Layer 1] has existing data in satellite_data? → skip (no GEE call)
  [Layer 2] is in backfill_skipped backlog? → skip (permanent, no GEE call)
  [Layer 3] select_best_scene() → if skip: write to backlog; else: extract → ingest
```

## 4. Files

| File | Action |
| :--- | :--- |
| `03_Build/historical_backfill.py` | New |
| `04_Test/result_output/historical/` | Created |
| `canopysense.backfill_skipped` | New PostGIS table |
| All core_engine + ingest modules | Zero change |

---

*Migrated from legacy `CDC-IMPL-002-v0.5`.*
