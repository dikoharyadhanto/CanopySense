# CDC-WALK-003-v0.2 — Technical Walkthrough

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-003-v0.2`. **Migrated from legacy** `CDC-WALK-003-v0.9`.

## 1. Scope

Full rewrite of Patcher-Local for production resilience: dual trigger modes, Option B block delivery, batch retry with `patcher_run_log` memory, exponential backoff, circuit breaker, IN_PROGRESS orphan recovery.

**Design principle:** Patcher-Local deployed once, never modified. All evolving logic lives in Patcher-Cloud.

## 2. Trigger Modes

| Mode      | Invocation                              | Scope                           |
|:--------- |:--------------------------------------- |:------------------------------- |
| Scheduled | `python3 patcher_local.py`              | All blocks, batched by afdeling |
| Upload    | `python3 patcher_local.py --block-id N` | Single block, immediate         |

## 3. Batch Resilience

| Mechanism           | Purpose                                                |
|:------------------- |:------------------------------------------------------ |
| `patcher_run_log`   | Tracks per-batch status; next run retries only failed  |
| IN_PROGRESS guard   | Prevents duplicate simultaneous runs                   |
| Exponential backoff | 30s → 60s → 120s on transient failures                 |
| Circuit breaker     | 3 consecutive 429 → 5-min pause                        |
| Presence check      | Success = block in `satellite_data` (not insert count) |

---

*Migrated from legacy `CDC-WALK-003-v0.9`.*
