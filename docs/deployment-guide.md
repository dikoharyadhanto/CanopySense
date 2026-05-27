# CanopySense — Deployment Guide (Phase 1)

## Prerequisites

- Docker (with PostGIS image available: `postgis/postgis:latest`)
- Python 3.11+ with pip
- Node.js 20+
- Git

---

## 1. Clone & Configure Environment

```bash
git clone <repo-url>
cd CanopySense
cp .env.example .env   # edit as needed
```

Key variables (see `docs/env-reference.md` for full list):
- `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`
- `SECRET_KEY` — change for production
- `VITE_API_URL` — backend URL seen by browser

---

## 2. Start Database (Docker)

```bash
# Start PostGIS container (port 5432)
docker run -d \
  --name canopy-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=canopysense \
  -p 5432:5432 \
  postgis/postgis:latest

# Wait ~5s for DB to initialize
sleep 5

# Apply schema
docker cp database/schema.sql canopy-db:/tmp/schema.sql
docker exec canopy-db psql -U postgres -d canopysense -f /tmp/schema.sql

# Load seed data (1 company, 1 estate, 44 blocks, ~2300 satellite rows)
docker cp database/seed.sql canopy-db:/tmp/seed.sql
docker exec canopy-db psql -U postgres -d canopysense -f /tmp/seed.sql
```

Verify:
```bash
docker exec canopy-db psql -U postgres -d canopysense \
  -c "SELECT COUNT(*) FROM canopysense.blocks; SELECT COUNT(*) FROM canopysense.satellite_data;"
# Expected: 44 blocks, ~2324 satellite rows
```

---

## 3. Start Backend (FastAPI)

```bash
cd backend
python3 -m venv venv
# Python 3.14: use pip3 --pre flag for pre-release wheels
pip3 install --pre fastapi uvicorn asyncpg pydantic pydantic-settings \
                   python-jose passlib python-dotenv python-multipart

PGHOST=localhost PGPORT=5432 PGUSER=postgres PGPASSWORD=postgres \
PGDATABASE=canopysense \
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify:
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

---

## 4. Start Frontend (Vite)

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
# Dev server: http://localhost:3000
```

For production build:
```bash
npm run build
# Artifacts in frontend/dist/ — serve with nginx or any static server
```

---

## 5. Login

Open `http://localhost:3000` in browser.

- **Username:** `manager`
- **Password:** `password` (bcrypt hash stored in seed; invalid passwords are rejected by the API)

---

## 6. Docker Compose (Full Stack)

See `docker-compose.yml` at project root for a single-command startup:

```bash
docker compose up --build
# Services: db (5432), api (8000), frontend (3000)
```

> **Status:** Validated locally. The frontend image uses `node:20-slim` to avoid Alpine/musl native binding issues with Vite/Rolldown.

---

## Notes

- IDCloudHost server deployment is post-Phase 1. The guide above covers local development.
- Patcher-cloud (GCP Cloud Function) network validation to IDCloudHost port 5432 is deferred (RR-004).
- TC-07 operational run uses `patcher_local.py` -> patcher-cloud and requires a valid `PATCHER_API_KEY`. The separate `tests/run_test.py` direct GEE->GCS harness may still require `storage.objects.create` on bucket `canopy-sense-data`; see `docs/env-reference.md`.
