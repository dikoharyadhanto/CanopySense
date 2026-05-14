# ANT-STR-003-v0.1 — Test Plan (STR)

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-003-v0.1`. **Migrated from legacy** `ANT-STR-003-v0.7`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Test Plan (STR) |
| **Version** | v0.1 |
| **Status** | COMPLETE |

## 2. Test Phases

| Phase | Description | Key Criteria | Result |
| :--- | :--- | :--- | :---: |
| A | Code audit — Patcher-Local security | No hardcoded keys, no GEE imports, <150 lines | ✅ |
| B | Cloud Function + Secret Manager auth | 401 on missing key, 403 on revoked key, 200 on ACTIVE key | ✅ |
| C | API key revocation latency | <30 seconds to deny next request | ⏳ Deferred |
| D | Level 1 local simulation | Mock Cloud Function → Patcher-Local → local PostGIS (5 rows) | ✅ |
| E | GUIDANCE.md operational review | Non-technical staff can deploy from docs alone | ⏳ Deferred |

## 3. Deferred Items (v0.8)

- Phase C (revocation latency measurement) → pending contractor PostGIS readiness
- Phase E (GUIDANCE review) → pending operations staff availability

---

*Migrated from legacy `ANT-STR-003-v0.7`. Deferred tasks covered by `ANT-WO-003-v0.8` (pending).*
