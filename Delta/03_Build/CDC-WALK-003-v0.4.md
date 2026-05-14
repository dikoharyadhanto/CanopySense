# CDC-WALK-003-v0.4 — Technical Walkthrough

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-003-v0.4`. **Consolidated from legacy** `CDC-WALK-003-v0.10b`.

## 1. Status: PARTIAL

| Item                        | Status                                         |
|:--------------------------- |:----------------------------------------------:|
| A — Docker test infra       | ✅ Walkthrough approved, implemented, validated |
| B — Revocation verification | ⏸️ No walkthrough — deferred                   |
| C — GEE Viewer endpoint     | 🛑 No walkthrough — on hold                    |

## 2. Item A — Docker Test Infrastructure

Two-container setup mirrors real deployment:

```
postgis container (port 5433→5432)
  ├─ init.sql: CREATE SCHEMA canopysense → blocks, satellite_data, patcher_write_test
  └─ Healthcheck: pg_isready

patcher container (depends_on postgis)
  ├─ COPY 03_Build/ → /app/
  ├─ env: PGHOST=postgis, PGDATABASE=canopysense_test
  └─ CMD: python3 patcher_local.py
```

Validation: `docker-compose up -d postgis && docker-compose run --rm patcher` → Phase D passes with mock_cloud.py.

---

*Consolidated. See WO-003 v0.4 for full scope.*
