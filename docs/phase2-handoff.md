# CanopySense — Phase 2 Handoff Notes

**Status:** Phase 1 complete (local dev stack operational)  
**Prepared by:** DEV — Sigma DEV-EXEC v1.1  
**Date:** 2026-05-25

---

## What Phase 1 Delivered

| Component | Status | Notes |
| :--- | :--- | :--- |
| PostgreSQL schema (15 tables, PostGIS) | Done | `database/schema.sql` |
| Seed data (1 company, 44 blocks, ~2,324 satellite rows) | Done | `database/seed.sql` |
| FastAPI backend (`/health`, `/auth/login`, `/api/blocks`, `/api/blocks/{id}/indices`) | Done | `backend/app/` |
| JWT auth with company_id isolation | Done | HS256, 7-day expiry |
| React+Vite frontend — login, dashboard map, time-series chart | Done | `frontend/src/` |
| Leaflet map with color-ramp vegetation index visualization | Done | `frontend/src/components/MapView.tsx` |
| Recharts time-series with cloud-cover flagging | Done | `frontend/src/components/TimeSeriesChart.tsx` |
| Local deployment guide | Done | `docs/deployment-guide.md` |

**Not yet complete (blocked or deferred):**
- TC-07: GEE pipeline export — blocked on IAM (`storage.objects.create` on `canopy-sense-data`). See `docs/env-reference.md`.
- Dockerfiles: `backend/Dockerfile`, `frontend/Dockerfile` — deferred, local-first approach.
- `docker compose up` full-stack test (TC-030) — deferred until Dockerfiles done.
- IDCloudHost server deployment — post-Phase 1.

---

## Phase 2 Priorities

### P1 — Complete Phase 1 Deferred Items

1. **TC-07 IAM fix**: Grant `storage.objects.create` to `canopysense@swm-ui.iam.gserviceaccount.com` on `canopy-sense-data`. Run GEE pipeline to validate end-to-end data ingestion.
2. **Dockerfiles**: Write `backend/Dockerfile` and `frontend/Dockerfile`. Validate `docker compose up --build` locally before server deployment.
3. **IDCloudHost deployment**: Migrate local Docker stack to IDCloudHost NVME 5. Point `VITE_API_URL` at server IP/domain.

### P2 — ML Pipeline (GCC Prediction)

The schema is ready (`ground_truth`, `predictions`, `anomalies`). Phase 2 adds:

1. **Ground truth collection**: Field measurement pipeline → `ground_truth` table.
2. **Model training**: GCC regression using NDVI/EVI/NDRE/SAVI/GNDVI features.
3. **Inference pipeline**: Patcher-cloud Cloud Function writes to `predictions` on new satellite ingestion.
4. **Anomaly detection**: Compare `gcc_predicted` vs `actual_gcc`; flag deviations → `anomalies`.

### P3 — Alert System

1. **Alert generation**: On anomaly creation, generate `alerts` rows for relevant users.
2. **API endpoints**: `GET /api/anomalies`, `GET /api/alerts`, `PATCH /api/alerts/{id}/read`.
3. **Frontend**: Notification bell, anomaly list view, alert detail page.

### P4 — Field Inspection Workflow

1. **Mobile-friendly inspection form**: Submit `field_inspections` from the field.
2. **Photo upload**: Store photo URLs in `field_inspections.photos` JSONB.
3. **Anomaly lifecycle**: OPEN → VERIFIED / FALSE_POSITIVE → RESOLVED status transitions.

### P5 — UI Polish and Multi-Tenancy

1. **Dashboard UI**: Design-system improvements (current UI is functional, not final).
2. **Company settings**: Per-company logo, theme, app title via `company_settings`.
3. **Invitation flow**: Token-based invite via `company_invitations` table.
4. **Role-based access**: Manager vs Viewer permission gating on frontend routes.
5. **Export**: CSV/XLSX download for vegetation index time series.

---

## Architecture Decisions to Carry Forward

| Decision | Rationale |
| :--- | :--- |
| `satellite_data` is append-only | Data integrity — historical indices must not be mutated. Trigger enforces this. |
| `company_id` denormalized on `blocks`, `afdelings`, `estates` | Fast tenant filter without joins up the hierarchy. |
| LATERAL JOIN for latest satellite data per block | Single query for all blocks + latest index — avoids N+1. |
| GCP patcher-cloud → IDCloudHost PostgreSQL | GEE pipeline runs on GCP; data lands in IDCloudHost DB via network (RR-004 pending validation). |
| asyncpg (not SQLAlchemy) | Raw async performance; JSONB/geometry columns need explicit parsing. |
| `ndre = NULL` for Landsat-8 | Band 6 (Red Edge) not available on Landsat-8. Frontend uses `connectNulls=false` to avoid interpolating gaps. |

---

## Known Technical Debt

| Item | Location | Impact |
| :--- | :--- | :--- |
| `password = 'dummy_hash'` in seed | `database/seed.sql` | Phase 1 only — any password accepted via bcrypt fallback. Must be replaced with real hashes before production. |
| Mock token fallback in Login | `frontend/src/pages/Login.tsx` | DEV mode only (`import.meta.env.DEV`). Disabled in production builds. |
| No rate limiting on `/auth/login` | `backend/app/auth/routes.py` | Add before public deployment. |
| CORS wildcard (`*`) in main.py | `backend/app/main.py` | Lock down to frontend origin before production. |
| No HTTPS termination | local dev | Add nginx/TLS in IDCloudHost deployment. |

---

## Key File Map

```
CanopySense/
├── database/
│   ├── schema.sql          # Full 15-table schema
│   └── seed.sql            # 1 company, 44 blocks, ~2,324 satellite rows
├── backend/
│   └── app/
│       ├── main.py         # FastAPI app, CORS, router mounts
│       ├── database.py     # asyncpg pool, settings
│       ├── auth/
│       │   ├── jwt.py      # create_access_token, verify_password
│       │   └── routes.py   # POST /auth/login
│       └── api/
│           ├── blocks.py   # GET /api/blocks, GET /api/blocks/{id}/indices
│           └── deps.py     # get_current_user JWT dependency
├── frontend/src/
│   ├── App.tsx             # Routes: /login, /dashboard, /timeseries
│   ├── lib/api.ts          # Axios instance with JWT interceptor
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── Dashboard.tsx   # Map + sidebar
│   │   └── TimeSeries.tsx  # Time-series chart page
│   └── components/
│       ├── MapView.tsx     # Leaflet + GeoJSON + color ramp
│       ├── TimeSeriesChart.tsx  # Recharts line chart
│       └── IndexSelector.tsx    # NDVI/EVI/NDRE/SAVI/GNDVI toggle
└── docs/
    ├── deployment-guide.md
    ├── env-reference.md
    ├── schema-documentation.md
    ├── api-reference.md
    └── phase2-handoff.md   ← this file
```

---

## Contacts and External Systems

| System | Details |
| :--- | :--- |
| GCP Project | `swm-ui` |
| GEE Service Account | `canopysense@swm-ui.iam.gserviceaccount.com` |
| GCS Bucket | `canopy-sense-data` |
| patcher-cloud Cloud Function | `DB_CONNECTION_STRING` → IDCloudHost PostgreSQL port 5432 |
| IDCloudHost Server | NVME 5 — main production server (deployment pending) |
| GCP Cloud Logging | Pipeline execution logs |
