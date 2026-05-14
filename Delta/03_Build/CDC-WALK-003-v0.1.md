# CDC-WALK-003-v0.1 — Technical Walkthrough

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-003-v0.1`. **Migrated from legacy** `CDC-WALK-003-v0.7`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Walkthrough (WALK) |
| **Version** | v0.1 |
| **Status** | APPROVED — Implementation Complete |

## 2. Architecture

```
Contractor Server                    Google Cloud
─────────────────                    ────────────
patcher_local.py  ───HTTPS POST───▶  patcher_cloud (GCF)
       │            X-API-Key: xxx      │
       │                                ├─ Secret Manager (key registry)
       │                                ├─ engine_launcher (core engine)
       │                                └─ CSV records → JSON response
       │
       ▼
  PostGIS ← write results
  (satellite_data)
```

## 3. Patcher-Local Flow

```
.env → load env vars
  → POST to Cloud Function (X-API-Key header)
  → receive JSON response
  → parse records array
  → execute_values() to PostGIS (ON CONFLICT DO NOTHING)
```

## 4. Security

- Patcher-Local: zero GEE imports, zero hardcoded keys
- Patcher-Cloud: API key validated per-request against Secret Manager
- Kill-switch: edit Secret Manager JSON only — no code redeployment

---

*Migrated from legacy `CDC-WALK-003-v0.7`.*
