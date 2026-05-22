---
name: ANT-STR-003-v0.8
project: Canopy Sense
status: PENDING — Planned for execution after contractor PostGIS server is ready
version: 0.8
created_date: 2026-04-20
prerequisite: ANT-STR-003-v0.7 Level 2 PASSED (2026-04-20)
linked_wo: ANT-WO-003-v0.8
---

# ANT-STR-003-v0.8 (Test Plan — Revocation Flow & Operational Readiness)

> [!NOTE]
> **Status:** This Test Plan is **PENDING**. Execution deferred until contractor PostGIS server is ready.
> Phases A, B, D, F from ANT-STR-003-v0.7 are already PASSED. This plan covers only the two deferred phases.

---

## 1. Scope

This test plan covers two verification phases deferred from ANT-STR-003-v0.7:

| Phase | Description | Dependency |
|-------|-------------|------------|
| **C** | API key revocation flow — empirical latency measurement | Secret Manager write access |
| **E** | GUIDANCE.md operational review — self-service readiness | Ops staff / contractor available |

No new code is deployed. This is a verification-only test plan.

---

## 2. Pre-Conditions Before Execution

- [ ] `CONTRACTOR_TEST` is `ACTIVE` in `canopysense-api-key-registry` Secret Manager
- [ ] Cloud Function `patcher_cloud` is `ACTIVE` (no redeployment since Level 2)
- [ ] `patcher_local.py` returns 200 on a fresh run (baseline confirmed)
- [ ] Access to GCP Console or `gcloud` CLI to edit Secret Manager
- [ ] Access to Cloud Logging to verify audit entries
- [ ] `03_Build/GUIDANCE.md` is the latest version

---

## 3. Testing Execution

### Phase C: API Key Revocation Flow
**Goal:** Verify that revoking a contractor's API key in Secret Manager immediately denies access — no code redeployment required.

**Execution Steps:**

**Step C-1: Baseline Confirmation**
```bash
# Run patcher_local — must return 200 with rows
cd /path/to/project
set -a && source 04_Test/.env && set +a
python3 03_Build/patcher_local.py
```
Expected: `[INFO] — Received N record(s) from Cloud Function.`

**Step C-2: Record Start Time**
```bash
date +"%H:%M:%S"   # note this timestamp
```

**Step C-3: Revoke the Key in Secret Manager**

Option A — via GCP Console:
1. Go to Secret Manager → `canopysense-api-key-registry` → latest version
2. Copy current JSON, edit `CONTRACTOR_TEST.status` from `"ACTIVE"` to `"REVOKED"`
3. Add `"revoked_date": "<today>"` to the `CONTRACTOR_TEST` entry
4. Save as new version

Option B — via gcloud CLI:
```bash
# Get current registry, edit, re-upload
~/google-cloud-sdk/bin/gcloud secrets versions access latest \
  --secret=canopysense-api-key-registry \
  --project=canopysense > /tmp/registry_backup.json

# Edit /tmp/registry_backup.json: set CONTRACTOR_TEST.status = "REVOKED"
# Then:
~/google-cloud-sdk/bin/gcloud secrets versions add canopysense-api-key-registry \
  --data-file=/tmp/registry_edited.json \
  --project=canopysense
```

**Step C-4: Immediately Re-run patcher_local**
```bash
python3 03_Build/patcher_local.py
```
Expected: `[ERROR] — Cloud Function HTTP error: 403 — {"error": "403 Forbidden: API Key revoked (issued ..., revoked ...)"}`

**Step C-5: Record End Time**
```bash
date +"%H:%M:%S"   # compute elapsed seconds
```

**Step C-6: Verify Cloud Logging Audit Entry**
In GCP Console → Cloud Logging → filter by:
```
resource.type="cloud_run_revision"
jsonPayload.audit=true
jsonPayload.status="REJECTED"
jsonPayload.contractor_id="CONTRACTOR_TEST"
```
Expected: Entry with `"detail": "Key revoked"` and timestamp matching Step C-4.

**Step C-7: Restore Key to ACTIVE**
Repeat Step C-3 but set `status` back to `"ACTIVE"` and remove `revoked_date`. Confirm `patcher_local.py` returns 200 again.

**Pass Criteria:**
1. Step C-4 returns 403 with exact message: `403 Forbidden: API Key revoked (issued ..., revoked ...)`
2. Elapsed time (C-2 to C-4) is **<30 seconds**
3. No Cloud Function redeployment was performed
4. Cloud Logging shows REJECTED audit entry with contractor_id + timestamp
5. Key restored to ACTIVE and confirmed working

**Failure Cases:**
- 403 not returned → **REJECT** (revocation not working)
- Elapsed time >30 seconds → **INVESTIGATE** (Secret Manager propagation delay — log actual value)
- Cloud Logging entry missing → **REJECT** (audit trail broken)

---

### Phase E: GUIDANCE.md Operational Review
**Goal:** Verify that `03_Build/GUIDANCE.md` enables self-service deployment, operation, and troubleshooting without CDC assistance.

**Execution Method:**
Have a person unfamiliar with the project internals (operations staff, contractor, or ANT acting as first-time reader) follow GUIDANCE.md without asking CDC.

**Step E-1: Section A — Setup**
Follow Section A instructions to simulate onboarding a new contractor:
- Locate the `.env.example` template
- Fill it with test values
- Verify IAM setup instructions are clear (exact gcloud commands present)
- Verify the Cloud Function URL is documented

Pass: Setup completable in <30 minutes without CDC.

**Step E-2: Section B — Normal Operations**
Follow Section B to simulate a manual trigger:
- Find the command to run `patcher_local.py` manually
- Verify the "check if run succeeded" steps are clear (PostGIS query provided)

Pass: Manual trigger and verification completable without CDC.

**Step E-3: Section C — Troubleshooting (2 Scenarios)**

Scenario 1 — Cloud Function returns 403:
- Follow GUIDANCE.md Section C steps for "Cloud Function returns 403"
- Verify the cause (invalid/revoked key) and resolution are documented

Scenario 2 — PostGIS connection failure:
- Simulate by temporarily setting wrong `PGHOST` in `.env`
- Follow GUIDANCE.md Section C for "PostGIS insert failed"
- Verify GUIDANCE.md identifies the cause and gives resolution steps

Pass: Both scenarios resolved using GUIDANCE.md only.

**Step E-4: Section D — Security**
Read Section D. Verify:
- Why API keys must not be committed to git
- How to store API key securely (environment only)
- Rotation recommendation (quarterly)

Pass: Security rationale is clear to a non-technical reader.

**Step E-5: Section E — Access Control**
Read Section E. Verify:
- Contractor understands what revocation means (instant 403)
- Process to request a new key after revocation is documented
- Steps to take if key is suspected compromised

Pass: Access control lifecycle is fully documented.

**Step E-6: Section F — Disaster Recovery**
Read Section F. Verify:
- What to do if Cloud Function is down
- Retry guidance (how long before escalating)
- Emergency contact or escalation path

Pass: Contractor knows what to do in a failure scenario.

**Step E-7: Glossary & Checklists**
- Verify glossary defines: API Key, Secret Manager, Cloud Function, Patcher-Local, Patcher-Cloud, revocation, PostGIS, bore tunnel (if referenced)
- Verify all checklists use exact copy-paste commands (no `<placeholder>` ambiguity in runnable steps)

Pass: All terms defined; checklists are self-contained.

**Pass Criteria:**
1. All 6 sections (A–F) reviewable without CDC
2. Both troubleshooting scenarios resolved using GUIDANCE.md only
3. Glossary covers all technical terms
4. Checklists are copy-paste safe
5. At least 1 worked example per section (command output or expected result)
6. Total time to complete review: <1 hour

**Failure Cases:**
- Any section requires CDC knowledge to complete → **REJECT** (document gap — CDC must update GUIDANCE.md)
- Troubleshooting steps lead to wrong action → **REJECT** (incorrect guidance)
- Glossary missing terms → **FLAG** (update required, not hard reject if minor)

---

## 4. Observations & Output

*(Fill during execution — leave blank until WO is activated)*

### Phase C: API Key Revocation

| Checkpoint | Result | Notes |
|------------|--------|-------|
| C-1 Baseline (200 OK) | PENDING | |
| C-3 Secret Manager edit time | PENDING | Timestamp: |
| C-4 403 returned | PENDING | Timestamp: |
| Revocation latency (C-2 to C-4) | PENDING | Target: <30s. Actual: |
| C-6 Cloud Logging REJECTED entry | PENDING | |
| C-7 Key restored to ACTIVE | PENDING | |

### Phase E: GUIDANCE.md Review

| Section | Pass/Fail | Gaps Found |
|---------|-----------|------------|
| A — Setup | PENDING | |
| B — Normal Operations | PENDING | |
| C — Troubleshooting (scenario 1) | PENDING | |
| C — Troubleshooting (scenario 2) | PENDING | |
| D — Security | PENDING | |
| E — Access Control | PENDING | |
| F — Disaster Recovery | PENDING | |
| Glossary | PENDING | |
| Checklists | PENDING | |
| Total review time | PENDING | Target: <1 hour. Actual: |

---

## 5. Success Criteria Summary

| Category | Criteria | Target | Result |
|----------|----------|--------|--------|
| **Revocation Speed** | 403 returned after key revoked | <30 seconds | PENDING |
| **Revocation Integrity** | No redeployment required | Zero deployments | PENDING |
| **Audit Trail** | Cloud Logging shows REJECTED entry | Present | PENDING |
| **Self-Service** | GUIDANCE.md enables full setup without CDC | <1 hour | PENDING |
| **Completeness** | All 6 GUIDANCE.md sections pass review | 100% | PENDING |

---

**ANT (Technical Foreman) Sign-off**: PENDING

**Activation Trigger:**
- Contractor PostGIS server ready, OR
- ANT decides to execute independently (Task C has no contractor dependency)
