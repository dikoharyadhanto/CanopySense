---
name: CDC-IMPL-003-v0.7
project: Canopy Sense
phase: Tahap III — Two-Patcher Architecture with Per-Contractor Access Control
status: COMPLETE — AWAITING ANT TEST EXECUTION
version: 0.7
created_date: 2026-04-20
---

# CDC-IMPL-003-v0.7 (Implementation Log)

---

## 1. Deliverables Summary

| Deliverable | File | Lines | Status |
|-------------|------|-------|--------|
| Patcher-Local script | `03_Build/patcher_local.py` | 148 | ✅ Complete |
| Patcher-Cloud function | `03_Build/patcher_cloud_function.py` | 172 | ✅ Complete |
| Cloud requirements | `03_Build/requirements_cloud.txt` | 17 | ✅ Complete |
| Env template | `03_Build/.env.example` | 29 | ✅ Complete |
| Operations guide | `03_Build/GUIDANCE.md` | ~270 | ✅ Complete |

All files reside within `03_Build/` per Isolation Constraint.
Zero modifications to existing files (`core_engine/`, `ingestion/`, `engine_launcher.py`, `historical_backfill.py`).

---

## 2. Implementation Decisions

### 2.1 Core Engine Invocation (FLAG-1 Resolution)
`patcher_cloud_function.py` imports `engine_launcher` as a module (not subprocess) and monkey-patches `engine_launcher._OUTPUT_DIR` to a writable `/tmp/cs_output_*` temp directory before calling `run_pipeline()`.

**Why module import over subprocess:**
- `engine_launcher._OUTPUT_DIR` is hardcoded to `_PROJECT_ROOT / "04_Test" / "result_output"` — in a Cloud Function this path is not writable
- Subprocess cannot patch a module constant without modifying the source file
- Direct import + monkey-patch is the only way to redirect output without touching engine_launcher.py (WO constraint: no core engine changes)
- Exception handling is cleaner and timeout control via `signal.SIGALRM` works reliably

**Approved by ANT:** FLAG-1 confirmed → use `engine_launcher.py` as entry point.

### 2.2 Data Return Flow
Cloud Function returns the processed CSV records as a JSON array in the response body:
```json
{
  "status": "success",
  "records": [...satellite data rows as CSV-parsed dicts...],
  "rows_returned": 84
}
```
Patcher-Local receives this array, parses each row, and inserts to local PostGIS via `psycopg2.extras.execute_values()` with `ON CONFLICT (block_id, acquisition_date, sensor) DO NOTHING` (PPX Risk 3).

**Rationale:** The contractor's local PostGIS is the reporting database. The cloud engine generates the data but the contractor needs it locally. Embedding records in the HTTP response avoids a separate GCS download step and keeps Patcher-Local dependency-free (no GCS client needed).

### 2.3 Secret Manager — No In-Memory Registry Caching (PPX Risk 1)
`_fetch_registry()` is called on every HTTP request. The Secret Manager **client** (`_SECRET_CLIENT`) is module-level (reused for connection pooling), but the **registry JSON** is always fetched fresh. This ensures a revoked key is denied on the very next call.

### 2.4 Rate Limiting (FLAG-2 Resolution)
Deferred per ANT decision. No in-memory rate limiter implemented. The `429` test case in ANT-STR Phase B is marked N/A for v0.7. Cloud Armor recommended for production.

### 2.5 IP Whitelist (FLAG-3)
Implemented as optional defense-in-depth: the whitelist check only runs when `ip_whitelist` is non-empty in the contractor's registry record. Uses `ipaddress.ip_network()` for CIDR matching. Relies on `X-Forwarded-For` header (advisory — documented caveat in GUIDANCE.md Section D).

### 2.6 Timeout Handling
`signal.SIGALRM` used for core engine timeout (Linux/macOS only — Cloud Functions run on Linux, so this is safe). Timeout value read from `FUNCTION_TIMEOUT_SECONDS` env var (default 120s). `signal.alarm(0)` always called in `finally` block to prevent alarm carry-over across warm invocations.

### 2.7 Retry Logic (Patcher-Local)
Single retry with 5-second backoff, per WO constraint ("retry once, fail gracefully"). `requests.exceptions.Timeout` triggers retry; `HTTPError` (4xx/5xx) does not retry (deterministic failures — retrying would not help).

---

## 3. Security Checklist (Self-Audit)

| Check | Result |
|-------|--------|
| Zero hardcoded API keys in patcher_local.py | ✅ All via `_require()` from env |
| Zero hardcoded API keys in patcher_cloud_function.py | ✅ All via Secret Manager |
| Zero GEE imports in patcher_local.py | ✅ No `ee` import |
| Secret Manager: no registry caching | ✅ Per-request fetch |
| PostGIS write: ON CONFLICT DO NOTHING | ✅ Both files |
| Timeout: env var controlled | ✅ `FUNCTION_TIMEOUT_SECONDS` |
| Error messages: helpful and specific | ✅ See ANT-STR Phase F table |
| All files in 03_Build/ | ✅ Isolation constraint met |

---

## 4. Line Count Verification

| File | WO Limit | Actual |
|------|----------|--------|
| `patcher_local.py` | <150 lines | 148 lines ✅ |
| `patcher_cloud_function.py` | <200 lines | 172 lines ✅ |

---

## 5. Error Message Compliance (ANT-STR Phase F)

| Scenario | Implemented Message | Status |
|----------|--------------------|----|
| Missing API key header | `401 Unauthorized: Missing X-API-Key header` | ✅ |
| Invalid API key | `403 Forbidden: Invalid API Key (contact administrator)` | ✅ |
| Revoked API key | `403 Forbidden: API Key revoked (issued {date}, revoked {date})` | ✅ |
| Cloud Function timeout | `504 Gateway Timeout: Core engine exceeded timeout (check Cloud Logging)` | ✅ |
| PostGIS connection failed | `500 Internal Server Error: PostGIS ingestion failed (reason in logs) — {pgcode}` | ✅ |
| Rate limit (429) | Deferred — N/A for v0.7 (ANT FLAG-2 decision) | N/A |

---

## 6. Dependencies Added

**Cloud Function (`requirements_cloud.txt`):**
- `functions-framework>=3.0.0` — Google Cloud Functions HTTP framework (new)
- `google-cloud-secret-manager>=2.16.0` — Secret Manager client (new)
- All other deps inherited from `requirements.txt` (no version changes)

**Contractor server (no new deps):**
- `requests`, `python-dotenv`, `psycopg2-binary` — already in `requirements.txt`

---

## 7. Known Limitations (v0.7 Scope)

1. **`last_used` field not updated in Secret Manager:** Writing back to Secret Manager requires creating a new secret version. For v0.7, `last_used` is updated via audit logs only. Production recommendation: use Firestore for mutable contractor state.

2. **Rate limiting deferred:** See FLAG-2. Cloud Armor is the production solution.

3. **SIGALRM timeout is Unix-only:** Cloud Functions run Linux — this is safe in production. Local Windows development requires a different timeout mechanism.

4. **Engine import side-effects:** Importing `engine_launcher` at the module level in the Cloud Function would initialize GEE connections on cold start. Import is deferred inside `_run_engine()` to avoid unnecessary cold start overhead.

5. **FLAG-T1 — Concurrency unsafe (single-instance constraint):** Both `signal.SIGALRM` and the `engine_launcher._OUTPUT_DIR` monkey-patch are process-global mutations. Under concurrent GCF requests on the same warm instance, two simultaneous invocations would race on the shared `_OUTPUT_DIR` value and the SIGALRM handler, producing corrupted output or premature timeouts. For v0.7, the Cloud Function **must** be deployed with `--max-instances=1` to prevent concurrent execution. Production v1.0 requires a thread-safe refactor (per-request temp-dir isolation via a context argument passed through the engine, and replacing `SIGALRM` with a `concurrent.futures.ThreadPoolExecutor` timeout pattern).

---

## 8. Files Created

```
03_Build/
├── patcher_local.py            ← Contractor trigger script (148 lines)
├── patcher_cloud_function.py   ← Cloud Function endpoint (172 lines)
├── requirements_cloud.txt      ← Cloud Function Python deps
├── .env.example                ← Configuration template for contractors
├── GUIDANCE.md                 ← Operations guide (6 sections A–F + glossary)
└── CDC-IMPL-003-v0.7.md        ← This file
```

---

**CDC (Lead Developer) — Implementation Complete**
**Date:** 2026-04-20
**Status:** AWAITING ANT TEST EXECUTION (ANT-STR-003-v0.7)
