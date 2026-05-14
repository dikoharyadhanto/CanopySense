# ANT-WO-003-v0.1 — Work Order

> [!IMPORTANT]
> **Dependencies**: `GMN-STRAT-001-v1.0`. **Migrated from legacy** `ANT-WO-003-v0.7`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Work Order (WO) |
| **Version** | v0.1 |
| **Status** | COMPLETE |
| **Legacy Source** | ANT-WO-003-v0.7 (2026-04-20) |
| **PPX Validation** | PASS WITH MINOR RISKS |

## 2. Scope — Two-Patcher Architecture

Build a two-patcher orchestration system: proprietary core engine isolated in Google Cloud, contractors use a thin stateless trigger script. Per-contractor API key authentication for selective access control.

### 2.1 Technical Tasks

**Patcher-Local (contractor-facing, ~148 lines):**
- Thin HTTP client — zero GEE imports, zero engine logic, zero hardcoded credentials
- Reads `PATCHER_API_KEY_{CONTRACTOR}` from `.env`
- Authenticated HTTP POST to Cloud Function URL
- Writes results to contractor's local PostGIS `satellite_data`
- `.env.example` provided as template

**Patcher-Cloud (Google Cloud Functions, 172 lines):**
- HTTP endpoint — validates `X-API-Key` against Secret Manager registry
- API key status check (ACTIVE/REVOKED)
- Triggers core engine via module import + monkey-patch
- Returns results JSON; logs all calls to Cloud Logging

### 2.2 Success Indicators

- Patcher-Local distributable without exposing core engine or API keys
- API key revocation disabled contractor access instantly (<30 seconds per PPX)
- All contractor calls auditable via Cloud Logging

### 2.3 Key Design Decisions

| Decision | Rationale |
| :--- | :--- |
| `patcher_cloud` imports `engine_launcher` as module (not subprocess) | `_OUTPUT_DIR` is not writable in Cloud Functions; monkey-patching the module constant redirects output without touching `engine_launcher.py` |
| Secret Manager registry fetched fresh per request | Revoked keys denied on very next call; no stale cache window |
| Records embedded in HTTP response body (not GCS) | Avoids GCS dependency in Patcher-Local |

## 3. Files Created

| File | Action |
| :--- | :--- |
| `03_Build/patcher_local.py` | New (148 lines) |
| `03_Build/patcher_cloud_function.py` | New (172 lines) |
| `03_Build/requirements_cloud.txt` | New |
| `03_Build/.env.example` | New |
| `03_Build/GUIDANCE.md` | New (~270 lines) |

---

*Migrated from legacy `ANT-WO-003-v0.7`. See `CDC-IMPL-003-v0.1` for full detail.*
