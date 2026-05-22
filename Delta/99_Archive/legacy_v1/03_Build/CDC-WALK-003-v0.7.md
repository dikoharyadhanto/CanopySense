---
name: CDC-WALK-003-v0.7
project: Canopy Sense
phase: Tahap III — Two-Patcher Architecture with Per-Contractor Access Control
status: ANT APPROVED — CLEARED FOR IMPLEMENTATION
version: 0.7
created_date: 2026-04-20
---

# CDC-WALK-003-v0.7 (Pre-Implementation Walkthrough)

> **To: ANT (Technical Foreman)**
> This is my pre-implementation plan for ANT-WO-003-v0.7. I am not starting any code until you explicitly approve this walkthrough.

---

## 1. Task Interpretation

### What Must Be Built
Based on ANT-WO-003-v0.7, I am building a **Two-Patcher Architecture** that separates contractor-facing logic from the proprietary core engine:

| Component | Location | Role |
|-----------|----------|------|
| `patcher_local.py` | `03_Build/` (contractor-facing) | Thin trigger script — reads `.env`, sends authenticated HTTP POST to Cloud Function, writes results to local PostGIS |
| `patcher_cloud_function.py` | `03_Build/` (deploy to Google Cloud Functions) | HTTP endpoint — validates API key against Secret Manager registry, triggers `core_engine_orchestrator.py`, returns results JSON |
| `.env.example` | `03_Build/` | Safe configuration template for contractors |
| `GUIDANCE.md` | `03_Build/` | Full operational documentation (6 sections A–F) for non-technical operations staff |

### What Must NOT Change
- Core engine files in `03_Build/core_engine/` — zero modifications (constraint from WO: "No changes from Phase 2")
- PostGIS schema — no schema changes
- `ingestion/ingest_to_postgis.py` — called as-is from Patcher-Local

### Security Boundary
- Patcher-Local: **zero GEE imports**, zero engine logic, zero hardcoded credentials
- Patcher-Cloud: receives raw API key over HTTPS, validates by hashing and comparing against Secret Manager registry (`sha256` comparison server-side)
- Kill-switch: edit Secret Manager JSON registry only — no code redeployment needed

---

## 2. Proposed Approach

### 2.1 Patcher-Local (`patcher_local.py`)

**Pattern:** Thin HTTP client with retry + graceful failure

**Flow:**
```
.env → load env vars
  → read trigger signal (manual or PostGIS scheduler call)
  → build POST request (API key in X-API-Key header, payload: contractor_id + run_config)
  → send to CLOUD_FUNCTION_URL (timeout from env: FUNCTION_TIMEOUT_SECONDS, default 120s)
  → on success: parse JSON response → call ingest_to_postgis with ON CONFLICT DO NOTHING
  → on failure: log error → retry once → fail gracefully (no silent swallow)
```

**Key decisions:**
- Dependencies: `requests`, `python-dotenv`, `psycopg2` only — no GEE, no engine imports
- Retry: single retry with 5s backoff (not exponential — WO says "retry once")
- PostGIS write: uses `ON CONFLICT DO NOTHING` upsert per PPX Risk 3
- Timeout: read from `FUNCTION_TIMEOUT_SECONDS` env var (default 120s) per PPX Risk 4
- Target: <150 lines (WO constraint)

### 2.2 Patcher-Cloud (`patcher_cloud_function.py`)

**Pattern:** Stateless HTTP Cloud Function, single endpoint

**Flow:**
```
HTTP POST received
  → check X-API-Key header present → 401 if missing
  → fetch API_KEY_REGISTRY from Secret Manager (versioned, no in-memory cache — PPX Risk 1)
  → sha256(received_key) → lookup in registry
  → if not found → 403 Invalid API Key
  → if status == REVOKED → 403 API Key revoked (with issued/revoked dates)
  → optional: validate source IP against ip_whitelist
  → trigger core_engine_orchestrator.py via subprocess
  → capture stdout JSON result
  → log call to Cloud Logging (contractor_id + timestamp + status)
  → return JSON response to caller
```

**Key decisions:**
- Secret Manager: fetch on every request — no caching (PPX Risk 1: prevents stale registry after revocation)
- Auth: sha256 comparison server-side only — raw key transmitted over HTTPS (PPX Risk 2: no client-side hashing)
- Timeout: configurable via `FUNCTION_TIMEOUT_SECONDS` env (PPX Risk 4)
- Core engine: invoked via `subprocess.run()` calling `core_engine_orchestrator.py`
- Rate limiting: return `429 Too Many Requests` with `Retry-After: 60` header (ANT-STR Phase B requirement)
- Target: <200 lines (WO constraint)

### 2.3 API Key Registry (Secret Manager JSON)

**Design confirmed from WO:**
```json
{
  "CONTRACTOR_ACME": {
    "api_key_hash": "<sha256 of raw key>",
    "status": "ACTIVE",
    "issued_date": "2026-04-20",
    "ip_whitelist": ["203.0.113.0/24"],
    "last_used": "2026-04-20T10:30:00Z"
  }
}
```

I will provide setup instructions in GUIDANCE.md Section A — not a script (config, not code).

### 2.4 GUIDANCE.md

**Audience:** Non-technical operations staff (no Python knowledge assumed)

**Structure (6 mandatory sections):**
- **Section A:** Deployment & Setup (IAM roles, `.env` config, connectivity test)
- **Section B:** Normal Operations (trigger run, verify success, expected runtime)
- **Section C:** Troubleshooting (403, timeout, PostGIS failure, Cloud Logging check)
- **Section D:** Security Best Practices (no `.env` in git, key rotation, monitoring)
- **Section E:** Access Control & Revocation (kill-switch flow, request new key, breach response)
- **Section F:** Disaster Recovery (Cloud Function down, retry escalation, manual fallback)
- **Glossary** of all technical terms
- **Checklists** in copy-paste safe format per section

---

## 3. Files to Create / Modify

All files inside `03_Build/` per Isolation Constraint.

| File | Action | Purpose |
|------|--------|---------|
| `03_Build/patcher_local.py` | **CREATE** | Contractor-facing trigger script |
| `03_Build/patcher_cloud_function.py` | **CREATE** | Cloud Function HTTP endpoint |
| `03_Build/.env.example` | **CREATE** | Safe config template for contractors |
| `03_Build/GUIDANCE.md` | **CREATE** | Full operational documentation (6 sections) |
| `03_Build/CDC-IMPL-003-v0.7.md` | **CREATE** (post-implementation) | Implementation log |

**No modifications** to existing files:
- `03_Build/core_engine/` — untouched
- `03_Build/ingestion/ingest_to_postgis.py` — called by reference, not modified
- `03_Build/engine_launcher.py`, `historical_backfill.py` — untouched

---

## 4. Dependencies

**Patcher-Local (contractor server, Python 3.8+):**
```
requests>=2.28.0        # HTTP client (already common)
python-dotenv>=1.0.0    # .env loader (already in requirements.txt)
psycopg2>=2.9.0         # PostGIS connector (already in requirements.txt)
```
No new packages needed — all already in `03_Build/requirements.txt`.

**Patcher-Cloud (Google Cloud Functions runtime, Python 3.10+):**
```
google-cloud-secret-manager>=2.16.0   # Secret Manager client
functions-framework>=3.0.0            # Google Cloud Functions framework
```
These are standard GCP libraries — added to a separate `requirements_cloud.txt` for the Cloud Function deployment.

**No new packages on contractor side** — this meets the WO constraint.

---

## 5. Flags / Risks

### FLAG-1: `core_engine_orchestrator.py` Does Not Exist Yet
**Observation:** ANT-WO-003-v0.7 Section 1.2 references triggering `core_engine_orchestrator.py` via subprocess inside Patcher-Cloud. Scanning `03_Build/core_engine/` — this file does **not exist**. The existing entry point is `03_Build/engine_launcher.py`.

**Risk:** Medium. If Patcher-Cloud calls a non-existent file, Phase D integration test will fail immediately.

**Proposed Resolution (Freedom of Method):** I will point Patcher-Cloud subprocess to `engine_launcher.py` instead of `core_engine_orchestrator.py`, since that is the confirmed existing entry point. **I need ANT explicit confirmation on this before implementing.**

---

### FLAG-2: Rate Limiting — No Built-in GCF Mechanism
**Observation:** ANT-STR-003-v0.7 Phase B requires a `429 Too Many Requests` response when rate limit is exceeded. Google Cloud Functions has no native per-IP rate limiting built into the function itself.

**Risk:** Low-Medium. Implementing rate limiting inside a stateless Cloud Function requires either (a) Firestore counter, (b) Cloud Armor / API Gateway, or (c) in-memory counter (unreliable across instances).

**Proposed Resolution:** I will implement a lightweight in-memory rate limiter with a documented caveat: it is per-instance only (not distributed). For production, ANT should add Cloud Armor. I will flag this in GUIDANCE.md. **ANT confirmation needed if in-memory approach is acceptable for v0.7 scope.**

---

### FLAG-3: IP Whitelist Validation — Optional per WO
**Observation:** WO Section 1.2 says "Optional: Verify request source IP against whitelist (if configured)." Cloud Functions receive source IP via `request.headers.get('X-Forwarded-For')` which can be spoofed at certain proxy layers.

**Risk:** Low. IP whitelist as an optional defense-in-depth layer — not the primary auth mechanism.

**Proposed Resolution:** I will implement IP whitelist check only when `ip_whitelist` field is non-empty in the registry. If empty/null → skip check. GUIDANCE.md will note the spoofing caveat.

---

### FLAG-4: Patcher-Local PostGIS Write — Schema Assumption
**Observation:** WO says Patcher-Local writes to `satellite_data` table using "standard ingestion flow." The existing `ingestion/ingest_to_postgis.py` contains the schema. I will call it directly to avoid schema drift.

**Risk:** Low. Existing module handles this.

**Proposed Resolution:** Call `ingest_to_postgis.py` as a module import from Patcher-Local (same server, same Python environment). This keeps the write logic DRY.

---

### FLAG-5: GUIDANCE.md — Cloud Function Deploy Steps Require GCP Project ID
**Observation:** GUIDANCE.md Section A must include exact `gcloud` commands for IAM setup. These commands reference a GCP Project ID that I don't have in the WO.

**Risk:** Low. Placeholder values are acceptable in documentation.

**Proposed Resolution:** Use `YOUR_PROJECT_ID` as a placeholder throughout GUIDANCE.md, with a clear instruction to replace it. This is standard practice in ops documentation.

---

## 6. Implementation Order (Proposed Sequence)

If ANT approves, I will implement in this order:

1. `.env.example` — establishes all required env var names as the contract
2. `patcher_cloud_function.py` — Cloud Function with auth + Secret Manager logic
3. `patcher_local.py` — Thin client referencing env vars defined in step 1
4. `GUIDANCE.md` — Full documentation (all 6 sections + glossary + checklists)
5. `CDC-IMPL-003-v0.7.md` — Implementation log (after code is complete)

---

## 7. Pre-Implementation Checklist (Self-Audit)

- [x] Patcher-Local: zero GEE imports confirmed in design
- [x] Patcher-Local: <150 lines target is achievable (thin HTTP client)
- [x] Patcher-Cloud: <200 lines target is achievable (single endpoint)
- [x] API key: raw key transmitted over HTTPS only, sha256 comparison server-side
- [x] Secret Manager: fetch per-request, no caching (PPX Risk 1)
- [x] PostGIS write: `ON CONFLICT DO NOTHING` (PPX Risk 3)
- [x] Timeout: `FUNCTION_TIMEOUT_SECONDS` env var (PPX Risk 4)
- [x] All files inside `03_Build/` (Isolation Constraint)
- [x] No core engine modifications
- [x] GUIDANCE.md: 6 sections planned
- [x] **FLAG-1: ANT APPROVED** — Use `engine_launcher.py` directly. No new orchestrator file needed.
- [x] **FLAG-2: ANT DECISION** — Skip rate limiting entirely in v0.7. In-memory approach rejected (false security). Deferred to Cloud Armor (production). ANT-STR updated accordingly.

---

**CDC (Lead Developer) — Submitted for ANT Review**
**Date:** 2026-04-20
**Status:** AWAITING ANT + USER APPROVAL — No code written yet
