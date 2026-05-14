# CDC-WALK-002-v0.1 — Technical Walkthrough

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-002-v0.1`. **Migrated from legacy** `CDC-WALK-002-v0.5`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Walkthrough (WALK) |
| **Version** | v0.1 |
| **Status** | APPROVED — Implementation Complete |

## 2. Scope

Build `historical_backfill.py` — standalone script that seeds `satellite_data` with 3 years of weekly historical satellite imagery (April 2023 → April 2026).

**Approach: Option A (weekly).** One best scene per 7-day chunk using existing `select_best_scene()` priority logic (S2 Tier 1 → S2 Tier 2 → Landsat → Skip). Rejected monthly chunks: frequency mismatch with live engine would break STL seasonal decomposition.

## 3. Execution Flow

```
Load blocks from canopysense.blocks
Initialize GEE, build AOI from block union

For each 7-day window in [Apr 2023 → Apr 2026] (~161 windows):
  select_best_scene(aoi_ee, date_start, date_end)
    → skip: log "No valid scene" → continue
    → found: cloud_mask → harmonize → indices
      extract CSV → 04_Test/result_output/historical/
      run_ingestion → PostGIS with ON CONFLICT DO NOTHING
```

## 4. Key Design Decisions

| Decision | Rationale |
| :--- | :--- |
| Weekly (not monthly) chunks | Live engine processes weekly — monthly would produce 1 obs/month vs 4 obs/month live, breaking STL seasonal decomposition |
| `backfill_skipped` backlog table | Permanently clouded-out windows recorded once; GEE quota not wasted on reruns |

---

*Migrated from legacy `CDC-WALK-002-v0.5`.*
