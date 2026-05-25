# CanopySense — Environment Variable Reference

## Backend (`backend/` — FastAPI)

| Variable | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `PGHOST` | `localhost` | Yes | PostgreSQL host |
| `PGPORT` | `5432` | Yes | PostgreSQL port |
| `PGUSER` | `postgres` | Yes | PostgreSQL username |
| `PGPASSWORD` | `postgres` | Yes | PostgreSQL password |
| `PGDATABASE` | `canopysense` | Yes | PostgreSQL database name |
| `SECRET_KEY` | `super_secret_key_change_me_in_production` | Yes | JWT signing key — **must change in production** |
| `ALGORITHM` | `HS256` | No | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` (7 days) | No | JWT expiry in minutes |

> `SECRET_KEY` must be a random, cryptographically strong string in any non-development environment.

## Frontend (`frontend/` — Vite)

| Variable | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `VITE_API_URL` | `http://localhost:8000` | Yes | Backend API base URL (seen by browser) |

In Vite, prefix all environment variables with `VITE_` to expose them to the client bundle.

## GCP / Pipeline

| Variable / Secret | Location | Description |
| :--- | :--- | :--- |
| `GEE_SERVICE_ACCOUNT_KEY` | GCP Secret Manager | Service account JSON key for Google Earth Engine access |
| `DB_CONNECTION_STRING` | GCP Secret Manager or `.env` | PostgreSQL connection string for patcher-cloud Cloud Function |
| GCS bucket `canopy-sense-data` | GCP Storage | Export destination for GEE pipeline output. Service account must have `storage.objects.create` permission. |

### IAM Remediation — TC-07 Blocker

TC-07 fails because the service account `canopysense@swm-ui.iam.gserviceaccount.com` lacks `storage.objects.create` on bucket `canopy-sense-data`.

Fix:
```bash
gcloud storage buckets add-iam-policy-binding gs://canopy-sense-data \
  --member="serviceAccount:canopysense@swm-ui.iam.gserviceaccount.com" \
  --role="roles/storage.objectCreator"
```

Or via GCP Console: Storage → Buckets → `canopy-sense-data` → Permissions → Grant `Storage Object Creator` to the service account.

After fix, re-run `tests/run_test.py` to confirm TC-07 passes.

## `.env.example`

```env
# Backend
PGHOST=localhost
PGPORT=5432
PGUSER=postgres
PGPASSWORD=postgres
PGDATABASE=canopysense
SECRET_KEY=change_me_in_production
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# Frontend
VITE_API_URL=http://localhost:8000
```
