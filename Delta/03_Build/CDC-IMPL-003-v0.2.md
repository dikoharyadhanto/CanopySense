# CDC-IMPL-003-v0.2 — Implementation Log

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-003-v0.2`. **Migrated from legacy** `CDC-IMPL-003-v0.9`.

## 1. Key Decisions

| Decision                       | Detail                                                                               |
|:------------------------------ |:------------------------------------------------------------------------------------ |
| Option B                       | Blocks as GeoJSON in request body; no Cloud Function DB connection                   |
| Conditional DB connection      | `engine_launcher.run_pipeline()` only opens DB when blocks not provided from request |
| `patcher_run_log` retry memory | Failed batches queried, placed at head of batch list for next run                    |
| IN_PROGRESS write-before-HTTP  | `started_at` stamped before HTTP call; 30-min stale → orphan recovery                |
| Exponential backoff            | 30s → 60s → 120s on transient failures                                               |
| Circuit breaker                | 3 consecutive 429 → 5-min pause                                                      |

## 2. Deliverables

| File                        | Lines | Action             |
|:--------------------------- | -----:|:------------------ |
| `patcher_local.py`          | 300   | Full rewrite       |
| `patcher_cloud_function.py` | 253   | Upgrade            |
| `deploy/main.py`            | 253   | Synced deploy copy |
| `deploy/engine_launcher.py` | 715   | Minimal update     |
| `patcher_run_log_ddl.sql`   | 31    | New                |
| `GUIDANCE.md`               | ~900  | Updated            |

## 3. Test Results: All phases PASSED (2 runs)

---

*Migrated from legacy `CDC-IMPL-003-v0.9`.*
