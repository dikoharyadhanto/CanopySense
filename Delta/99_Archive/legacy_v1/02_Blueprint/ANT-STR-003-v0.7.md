---
name: ANT-STR-003-v0.7
project: Canopy Sense
status: ACTIVE
version: 0.7
---

# ANT-STR-003-v0.7 (Test Plan - Two-Patcher Architecture with API Key Control)

## 1. Acceptance Rules

- Patcher-Local must be distributable to contractors without exposing proprietary code or API keys
- API key revocation must disable contractor access instantly (<30 seconds)
- Cloud Function must authenticate every request before triggering core engine
- GUIDANCE.md must enable any operations staff to deploy, operate, and troubleshoot without consulting CDC
- All contractor calls must be auditable (audit trail in Cloud Logging)

---

## 2. Testing Execution (Phases)

### Phase A: Code Audit — Patcher-Local Security
**Action:** Inspect `03_Build/patcher_local.py` for credential exposure.

**Pass Criteria:**
1. Zero hardcoded API keys (all via `.env` or environment variables)
2. Zero GEE imports (no IP logic visible)
3. Zero database credentials in code (all via `.env`)
4. Dependencies only: `requests`, `python-dotenv`, `psycopg2` (standard)
5. Code is <150 lines and single-purpose
6. `.env.example` provided (shows safe template)

**Failure Case:**
- If any API key, credential, or GEE logic is hardcoded → **REJECT** (security risk)

---

### Phase B: Cloud Function Setup & Authentication
**Action:** Deploy Patcher-Cloud to Google Cloud Functions and configure Secret Manager.

**Pass Criteria:**
1. Cloud Function HTTP endpoint is accessible (test with curl)
2. Secret Manager contains API_KEY_REGISTRY JSON with test keys:
   - `CONTRACTOR_TEST_A`: status = ACTIVE
   - `CONTRACTOR_TEST_B`: status = REVOKED
3. Patcher-Cloud reads Secret Manager on startup (no hardcoded values)
4. Requests without `X-API-Key` header return `401 Unauthorized`
5. Requests with invalid API key return `403 Forbidden`
6. Requests with ACTIVE API key proceed to core engine
7. Cloud Logging shows all calls (success + failures) with timestamp + contractor_id

**Test Commands (from terminal):**
```bash
# Valid key — use raw API key value from .env (PPX Risk 2: do NOT sha256 the key in actual calls)
curl -X POST \
  https://CLOUD_FUNCTION_URL \
  -H "X-API-Key: API_KEY_TEST_A_RAW_VALUE" \
  -H "Content-Type: application/json"

# Invalid key (should return 403)
curl -X POST \
  https://CLOUD_FUNCTION_URL \
  -H "X-API-Key: invalid-key" \
  -H "Content-Type: application/json"

# No key (should return 401)
curl -X POST \
  https://CLOUD_FUNCTION_URL \
  -H "Content-Type: application/json"

```
> **Note (PPX Risk 2 clarification):** Auth uses raw API key transmitted over HTTPS. The sha256 reference was removed — do not hash the key client-side. HTTPS transport encryption is sufficient.
> **Note (Rate Limiting — v0.7 N/A):** 429 rate limiting is NOT tested in v0.7. In-memory limiting is unreliable across stateless GCF instances (false protection). Deferred to Cloud Armor in production. See GUIDANCE.md Section A.

**Failure Case:**
- If any key is hardcoded in Cloud Function code → **REJECT**
- If Cloud Logging is not capturing calls → **REJECT**

---

### Phase C: API Key Revocation Flow
**Action:** Revoke a test API key and verify instant access denial.

**Pass Criteria:**
1. Test API key (CONTRACTOR_TEST_A) is ACTIVE in Secret Manager
2. Patcher-Local can call Cloud Function successfully (returns results)
3. Edit Secret Manager: set CONTRACTOR_TEST_A status to `REVOKED`
4. Re-run Patcher-Local call immediately (within 30 seconds)
5. Cloud Function returns `403 Forbidden: API key revoked`
6. Cloud Logging shows revoked key attempt with contractor_id + timestamp
7. No code redeployment was required (configuration-only change)
8. **Latency measurement (PPX recommendation):** Record actual revocation-to-deny time in seconds and log it in the Observations section below. Target: <30s. Result must be logged empirically (not assumed).

**Failure Case:**
- If revocation requires code changes or Cloud Function redeployment → **REJECT** (not instant)
- If old API key still works after revocation → **REJECT** (revocation failed)

---

### Phase D: End-to-End Integration Test
**Action:** Deploy Patcher-Local on a test contractor environment and run full pipeline.

**Pre-requisites:**
- Test contractor server (local machine + Docker PostGIS)
- Patcher-Local script deployed with `.env` configured
- Valid API_KEY_TEST in Secret Manager (ACTIVE)

**Pass Criteria:**
1. Patcher-Local reads trigger signal (manual call: `python patcher_local.py`)
2. Patcher-Local authenticates to Cloud Function with API key
3. Cloud Function receives request → validates key → triggers core engine
4. Core engine runs end-to-end extraction (Phase 1: weekly indices)
5. Results returned to Patcher-Local as JSON (success status + row count)
6. Patcher-Local writes results to test PostGIS `satellite_data` table
7. Query PostGIS: `SELECT COUNT(*) FROM canopysense.satellite_data;` returns new rows
8. Cloud Logging shows complete audit trail (request → auth → execution → response)

**Failure Case:**
- If Patcher-Local cannot authenticate → **REJECT** (integration broken)
- If PostGIS write fails → **REJECT** (ingestion issue)
- If Cloud Logging is incomplete → **REJECT** (audit trail missing)

---

### Phase E: GUIDANCE.md Operational Review
**Action:** Have a non-technical operations staff member (or yourself) follow GUIDANCE.md without consulting CDC.

**Pass Criteria:**
1. Section A (Setup): Follow instructions exactly, successfully configure Patcher-Local for a new contractor
2. Section B (Operations): Follow troubleshooting steps for a simulated error (e.g., "Cloud Function returns 403")
3. Section C (Troubleshooting): Resolve 2 common issues using GUIDANCE.md only
4. Section D (Security): Understand how API keys work and why they shouldn't be shared
5. Section E (Access Control): Understand how to request a new API key after revocation
6. Section F (Disaster Recovery): Know what to do if Cloud Function is down
7. Glossary: All technical terms are defined in plain English
8. Checklists: Copy-paste safe (no ambiguity, exact commands provided)
9. Examples: At least 1 worked example per section (command output, screenshot, or expected result)

**Test Method:**
- Print GUIDANCE.md
- Have someone unfamiliar with the project read it
- Ask them: "Can you deploy Patcher-Local to a test server? Can you revoke an API key?"
- Time it: should take <1 hour without needing CDC support

**Failure Case:**
- If GUIDANCE.md contains jargon without explanation → **REJECT**
- If a procedure requires CDC knowledge to complete → **REJECT** (not self-service)
- If GUIDANCE.md doesn't cover a common mistake → **REJECT** (incomplete)

---

### Phase F: Error Message Clarity
**Action:** Trigger each error scenario and verify messages are helpful.

**Pass Criteria:**

| Error Scenario | Expected Message | Helpful? |
|---|---|---|
| Missing API key header | `401 Unauthorized: Missing X-API-Key header` | ✅ Yes |
| Invalid API key | `403 Forbidden: Invalid API Key (contact administrator)` | ✅ Yes |
| Revoked API key | `403 Forbidden: API Key revoked (issued 2026-04-20, revoked 2026-04-25)` | ✅ Yes |
| Cloud Function timeout | `504 Gateway Timeout: Core engine exceeded timeout (check Cloud Logging)` | ✅ Yes |
| PostGIS connection failed | `500 Internal Server Error: PostGIS ingestion failed (reason in logs)` | ✅ Yes |
| Rate limit exceeded | `429 Too Many Requests` | ⏭️ N/A for v0.7 — deferred to Cloud Armor (production) |

**Failure Case:**
- If error messages are cryptic (e.g., "HTTPError 403") → **REJECT** (not helpful)

---

## 3. Observations & Output

**(This section to be updated during/after Lead Developer Execution)**

### Code Audit Results
- [ ] Patcher-Local security audit: **pending**
- [ ] Zero IP exposure confirmed: **pending**
- [ ] `.env.example` template provided: **pending**

### Cloud Function Setup
- [ ] Cloud Function deployed successfully: **pending**
- [ ] Secret Manager configured: **pending**
- [ ] Cloud Logging enabled: **pending**

### API Key Revocation Test
- [ ] Test key revocation time: **pending** (target: <30 seconds)
- [ ] Post-revocation call returns 403: **pending**

### End-to-End Integration
- [ ] Patcher-Local → Cloud Function call succeeds: **pending**
- [ ] Core engine execution completes: **pending**
- [ ] PostGIS ingestion successful: **pending**
- [ ] Audit trail in Cloud Logging complete: **pending**

### GUIDANCE.md Quality
- [ ] All 6 sections present: **pending**
- [ ] At least 1 worked example per section: **pending**
- [ ] Glossary complete: **pending**
- [ ] Checklists are copy-paste safe: **pending**
- [ ] Non-technical user can follow without CDC help: **pending**

### Error Messages
- [ ] All error scenarios tested: **pending**
- [ ] Messages are helpful (not cryptic): **pending**

---

## 4. Success Criteria Summary

| Category | Criteria | Target |
|----------|----------|--------|
| **Security** | Zero API keys in code | 100% |
| **Functionality** | End-to-end pipeline works | Pass all phases |
| **Operability** | GUIDANCE.md enables self-service | Non-tech user can use |
| **Auditability** | All calls logged | 100% coverage |
| **Speed** | API key revocation | <30 seconds |

---

**ANT (Technical Foreman) Sign-off**: 2026-04-20 (v0.7)

**Important Note for CDC:**
- GUIDANCE.md is as important as the code itself. A well-documented system prevents operational errors and contractor mistakes.
- This is your opportunity to teach how the system works to someone who may not know Python or Google Cloud.
- Invest time in clarity, examples, and checklists.
