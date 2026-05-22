---
name: ANT-WO-003-v0.7
project: Canopy Sense
phase: Tahap III (Deployment): Two-Patcher Architecture with Per-Contractor Access Control
status: ACTIVE
ppx_validation: PASS WITH MINOR RISKS (PPX-RES-000-v0.1.md — 2026-04-20)
ppx_validation_date: 2026-04-20
ppx_risks_addressed: Risk 1 (Secret Manager versioning), Risk 2 (raw key auth), Risk 3 (idempotent writes), Risk 4 (configurable timeout)
---

# ANT-WO-003-v0.7 (Work Order)

> [!IMPORTANT]
> **Lead Developer (Claude Code)**: You are granted "Freedom of Method" within the constraints of this Work Order.
> Goal: Build a two-patcher orchestration system that keeps core engine proprietary and isolated in Google Cloud, while giving contractors only a thin, stateless trigger script. Implement per-contractor API key authentication for selective access control.

---

## 1. Technical Tasks (Scope)

### 1.1 Patcher-Local Script (Contractor-Facing)
**File:** `03_Build/patcher_local.py` (new)

- Thin orchestration script (~100 lines max)
- No core engine logic, no index calculations, no GEE imports
- Reads trigger signal from PostGIS scheduler or manual call
- Retrieves `PATCHER_API_KEY_{CONTRACTOR}` from environment (`.env`)
- Sends authenticated HTTP POST to Cloud Function URL
- Waits for response JSON (results)
- Writes results to contractor's local PostGIS `satellite_data` table
- Includes minimal error handling (log, retry once, fail gracefully)
- **Zero hardcoded credentials** (all via `.env`)

**Input:**
- PostgreSQL connection string (local contractor DB)
- Cloud Function URL (environment variable)
- API Key (environment variable, issued per contractor)

**Output:**
- JSON response from Cloud Function (results metadata)
- Data inserted to PostGIS via standard ingestion flow

---

### 1.2 Cloud Function: Patcher-Cloud (Google Cloud)
**Location:** Google Cloud Functions (HTTP trigger)
**Language:** Python 3.10+

**Responsibilities:**
- Listen for HTTP POST from Patcher-Local
- Extract API Key from request header: `X-API-Key`
- Validate API Key against Secret Manager registry
- Verify API Key is **ACTIVE** (not revoked)
- Optional: Verify request source IP against whitelist (if configured)
- If auth fails → return `403 Forbidden` with reason
- If auth succeeds → trigger core engine orchestration (Python subprocess call to `core_engine_orchestrator.py`)
- Capture results JSON from core engine
- Return results to Patcher-Local
- Log all calls (success + failures) to Cloud Logging

**Environment Variables (from Secret Manager):**
- `API_KEY_REGISTRY` — JSON mapping of active/revoked API keys
- `GCS_BUCKET_CORE_ENGINE` — GCS path to core engine scripts
- `LOG_LEVEL` — DEBUG / INFO / ERROR

**Return Response (JSON):**
```json
{
  "status": "success",
  "timestamp": "2026-04-20T10:30:00Z",
  "rows_inserted": 84,
  "errors": [],
  "core_engine_logs": "..."
}
```

---

### 1.3 Per-Contractor API Key System
**Location:** Google Cloud Secret Manager

**Design:**
- Each contractor receives unique API_KEY_{CONTRACTOR} at deployment time
- Example: `API_KEY_ACME_FARMS = "gcp-sec-xxxx-yyyy-zzzz"`
- API Key registry stored as JSON in Secret Manager:
```json
{
  "CONTRACTOR_ACME": {
    "api_key_hash": "sha256(API_KEY_ACME)",
    "status": "ACTIVE",
    "issued_date": "2026-04-20",
    "ip_whitelist": ["203.0.113.0/24"],
    "last_used": "2026-04-20T10:30:00Z"
  },
  "CONTRACTOR_BETA": {
    "api_key_hash": "sha256(API_KEY_BETA)",
    "status": "REVOKED",
    "revoked_date": "2026-04-15",
    "reason": "contract terminated"
  }
}
```

**Key Operations:**
- **Issue:** Generate new API_KEY → store hash in registry → mark ACTIVE
- **Revoke:** Contractor ends → set status to REVOKED (instant, no code change needed)
- **Audit:** Log all API calls (success + failed attempts) with timestamp + contractor ID

---

### 1.4 Operational Kill-Switch Capability
**Requirement:** Foreman (you) can disable contractor access in <30 seconds without code changes

**Method 1 (Selective):**
- Edit Secret Manager `API_KEY_REGISTRY`
- Set contractor's API key status to `REVOKED`
- Next call from Patcher-Local → `403 Access Denied`

**Method 2 (Emergency):**
- Disable Cloud Function entirely (via Google Cloud Console)
- All contractors blocked immediately

**Audit Trail:**
- All revocation actions logged with timestamp + reason
- Failed API calls logged (detect tampering attempts)

---

### 1.5 Documentation: GUIDANCE.md (Critical)
**File:** `03_Build/GUIDANCE.md` (new, created by CDC)

**This document is mandatory and must cover:**

#### Section A: Deployment & Setup (for you or Contractor)
1. How to deploy Patcher-Local to contractor's server
2. `.env` configuration file template
3. How to securely set API_KEY (never in code/git)
4. How to test Patcher-Local connectivity to Cloud Function
5. Common setup mistakes (hardcoding keys, wrong URLs, missing permissions)
6. **Required IAM roles setup:** Cloud Function must have `roles/secretmanager.secretAccessor` assigned (step-by-step with screenshots or exact gcloud commands)

#### Section B: Normal Operations
1. How to trigger a single extraction run manually
2. How to check if a run succeeded (logs, PostGIS query)
3. How to interpret error messages
4. Expected runtime + data freshness
5. Monitoring dashboard / log location

#### Section C: Troubleshooting
1. "Cloud Function returns 403" → what it means (auth failed)
2. "Patcher-Local timeout" → network / API latency issue
3. "PostGIS insert failed" → connector issue
4. How to check Cloud Logging for server-side errors
5. How to manually verify core engine output

#### Section D: Security Best Practices
1. **Never commit `.env` to git**
2. **Never share API keys** (they're per-contractor)
3. **Keep API key in environment only** (not hardcoded)
4. **Rotate API keys periodically** (recommend: quarterly)
5. **Monitor Cloud Logging for suspicious calls**

#### Section E: Access Control & Revocation
1. How API key revocation works (from user perspective)
2. What happens when API key is revoked (instant 403)
3. How to request a new API key if lost/expired
4. Steps to take if you suspect a breach

#### Section F: Disaster Recovery
1. What to do if Cloud Function is down
2. How long to retry before escalating
3. Where to find backup logs
4. How to manually run core engine (if needed)

**Quality Standards (CDC must meet):**
- Clear, non-technical language for operations teams
- At least one worked example per section (screenshots / command output)
- Glossary of terms (API Key, revocation, Cloud Function, etc.)
- Checklist format for critical procedures (copy-paste safe)
- Links to relevant files + Google Cloud docs

---

## 2. Success Indicators

### Technical (Code-Level)
- [ ] Patcher-Local runs without GEE imports (zero IP exposure)
- [ ] Patcher-Cloud validates API key before triggering core engine
- [ ] API key revocation works (revoked key → 403 instantly)
- [ ] Cloud Logging captures all calls (audit trail present)
- [ ] Results returned to Patcher-Local in <10 seconds (latency acceptable)
- [ ] Patcher-Local successfully writes results to PostGIS

### Documentation (GUIDANCE.md)
- [ ] All 6 sections (A–F) present and complete
- [ ] At least 1 worked example per section
- [ ] Glossary covers all technical terms
- [ ] Checklists are copy-paste safe (no ambiguity)
- [ ] Links to external docs (Google Cloud, PostGIS) are correct
- [ ] No jargon without explanation

### Operational (Your Review)
- [ ] You can revoke a test API key in <30 seconds
- [ ] Revoked key returns 403 on next call
- [ ] Cloud Logging shows clear audit trail
- [ ] You understand how to deploy GUIDANCE.md to contractors

---

## 3. Implementation Constraints

### Architecture
- **IP Protection:** Core engine must remain in Google Cloud (GCS / Cloud Run / Cloud Function)
- **Contractor Transparency:** Patcher-Local is dumb + auditable (no hidden logic)
- **No Shared State:** Each contractor has independent API key + whitelist
- **Stateless Cloud Function:** No state stored in Cloud Function (all in Secret Manager)

### Security
- **API Key Storage:** Only in Secret Manager or `.env` (never in code)
- **Communication:** HTTPS only (Google Cloud enforces this)
- **Audit:** All calls logged with contractor ID + timestamp
- **Kill-Switch:** Revocation must work without redeployment
- **Secret Manager Versioning (PPX Risk 1 — Medium):** Patcher-Cloud must read Secret Manager using versioned secret references (`latest` pinned at startup, no in-memory caching of the JSON registry). This prevents partial-read issues during concurrent edits. If multi-admin writes are expected, use Firestore instead of Secret Manager JSON for the API key registry.
- **Idempotent PostGIS Writes (PPX Risk 3 — Medium):** Patcher-Local must use `ON CONFLICT DO NOTHING` (or equivalent upsert) for all PostGIS inserts. No partial ingestion is acceptable — if a write fails mid-batch, the operation must be retried without creating duplicate rows.
- **Cloud Function IAM (PPX Recommendation):** Cloud Function must be granted `roles/secretmanager.secretAccessor` IAM role. GUIDANCE.md Section A must document this IAM setup explicitly (non-negotiable for deployment to work).
- **Configurable Timeout (PPX Risk 4 — Low):** Do not hardcode 60s timeout. Set via environment variable `FUNCTION_TIMEOUT_SECONDS` (default: 120s). For long extractions, design Patcher-Cloud to invoke core engine asynchronously if timeout risk is detected.

### Compatibility
- **Patcher-Local:** Must work with Python 3.8+ (common on contractor servers)
- **Core Engine:** No changes from Phase 2 (Phase 1 only for now)
- **PostGIS:** Same ingestion flow as Phase 1/2 (no schema changes)

### Code Quality
- **Patcher-Local:** <150 lines, single-purpose, no dependencies beyond `requests` + `python-dotenv`
- **Patcher-Cloud:** <200 lines, single endpoint, clear error responses
- **GUIDANCE.md:** Written for non-technical operations staff (no Python knowledge assumed)

---

## 4. Deliverables Checklist

| Deliverable | Type | Owner | Status |
|------------|------|-------|--------|
| `03_Build/patcher_local.py` | Code | CDC | Pending |
| `patcher_cloud_function.py` | Code (deploy to Google Cloud) | CDC | Pending |
| Secret Manager API key registry setup (JSON) | Config | CDC | Pending |
| `03_Build/GUIDANCE.md` | Documentation | CDC | **Mandatory** |
| Unit tests for Patcher-Local | Tests | CDC | Optional (recommended) |
| Integration test (Patcher-Local → Cloud Function → PostGIS) | Tests | CDC | Pending |
| `.env.example` template | Config | CDC | Pending |

---

## 5. Notes for CDC

1. **Freedom of Method:** You decide how to structure `patcher_local.py` and Cloud Function logic, as long as you meet Success Indicators.
2. **GUIDANCE.md is not optional:** This is your chance to document how to use the system correctly. Poor guidance = operational errors by contractors. Invest time here.
3. **Test with a fake API key:** Before handing to contractors, verify revocation flow works (set a test key to REVOKED, call Cloud Function, expect 403).
4. **Error messages matter:** When API key is invalid, return `403 Forbidden: Invalid API Key (contact administrator)` (not a cryptic error code).
5. **Cloud Function cold start:** First call may take 3–5 seconds. Document this in GUIDANCE.md.

---

**ANT (Technical Foreman) Sign-off**: 2026-04-20 (v0.7)

**Next Steps:**
1. CDC creates pre-implementation walkthrough (CDC-WALK-003-v0.7)
2. ANT reviews walkthrough for correctness
3. CDC implements + creates GUIDANCE.md
4. ANT executes ANT-STR-003-v0.7 test plan
5. GUIDANCE.md reviewed by ANT for operational clarity
