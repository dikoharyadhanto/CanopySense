# CanopySense — Local Simulation Guide

**Purpose:** Demonstrate the full CanopySense data pipeline running entirely on a single laptop — no cloud subscription or remote server required.
**Audience:** Project team, potential contractors, stakeholders
**Last Updated:** 2026-04-20

---

## What This Simulation Demonstrates

This guide walks through a complete, working simulation of the CanopySense system running locally. By the end, you will see real satellite vegetation data (NDVI, EVI, and other indices) pulled from Google Earth Engine and stored in a local database — the same database a contractor would use in production.

The simulation covers the full chain:

```
Your Laptop
────────────────────────────────────────────────────────────
  [Patcher-Local]  →  [Cloud Function (local)]  →  [Google Earth Engine]
                                                         ↓
                              [Local PostGIS Database]  ←
────────────────────────────────────────────────────────────
```

The only external service used is **Google Earth Engine** (GEE) for fetching satellite imagery. Everything else — the trigger script, the processing function, and the database — runs on the same machine.

---

## Prerequisites

The following must be in place before starting. These are already configured on the project laptop.

| Component | Status | Details |
|-----------|--------|---------|
| Docker Desktop | Ready | Running the local PostGIS database |
| PostGIS container | Ready | Container: `canopy-project-repos`, port 5432 |
| Python 3.10+ | Ready | With all dependencies installed |
| `gcloud` authenticated | Ready | Allows the local simulator to reach Google Cloud Secret Manager for GEE credentials |
| `04_Test/.env` | Ready | Contains `EE_PROJECT_ID` and PostGIS connection settings |
| `04_Test/test_registry.json` | Ready | Local stand-in for the API key registry (explained below) |

---

### Why `gcloud` Authentication Is Needed (Local Simulation Only)

This is important to understand: **`gcloud` authentication is only required for the local simulation — not in production.**

Here is why:

In production, the code runs inside Google Cloud Functions. Google automatically attaches a **service account identity** to the Cloud Function (`78268232885-compute@developer.gserviceaccount.com`). This identity already has permission to access Secret Manager and fetch the GEE credentials. No login, no key file, no manual setup — it is handled entirely by Google Cloud infrastructure.

In local simulation, `functions-framework` runs the same code as a plain Python process on your laptop. Your laptop is not inside Google Cloud, so there is no service account attached. Instead, the code uses your laptop's existing `gcloud` login (called Application Default Credentials) to reach Secret Manager. This is a simulation-only workaround that mimics what the service account does automatically in production.

**In simple terms:**

| Environment | Who authenticates to Secret Manager? |
|-------------|--------------------------------------|
| Real Cloud Function (production) | Cloud Function's service account — automatic, no setup needed |
| Local simulation (this laptop) | Your `gcloud` login — already set up, used as a stand-in |

The contractor running `patcher_local.py` on their own server does not need `gcloud` at all. Their script only sends an HTTP request to the Cloud Function URL — everything else (authentication, GEE access, Secret Manager) happens inside Google Cloud on their behalf.

---

### What `test_registry.json` Is For

In production, the Cloud Function checks contractor API keys against a registry stored in Google Cloud Secret Manager. Running that check locally would mean every test call hits Secret Manager just to validate a test key — slow and unnecessary.

`test_registry.json` is a **local copy of that registry**, used only during simulation. It contains one entry: `CONTRACTOR_TEST` with the test API key `my-test-key-123` (stored as a SHA-256 hash). When the simulator starts, this file is loaded as an environment variable (`LOCAL_REGISTRY_JSON`), and the code uses it instead of calling Secret Manager for key validation.

The result: API key validation is handled locally and instantly, while GEE credential fetching still goes to the real Secret Manager. Both paths work exactly as they do in production — just with a local shortcut for the key registry.

---

If running this on a **different machine**, you will also need:
- Docker installed and running
- Python with: `pip install functions-framework requests python-dotenv psycopg2-binary earthengine-api geopandas`
- `gcloud` installed and authenticated with access to the `canopysense` GCP project

---

## Overview: Two Terminals, One Demo

This simulation requires **two terminal windows open at the same time**:

- **Terminal A** — runs the Cloud Function locally (stays open and listening)
- **Terminal B** — runs the trigger script that sends the request

Think of Terminal A as "the cloud server" and Terminal B as "the contractor's laptop."

---

## Step 1 — Start the Local Database

Open a terminal and confirm the PostGIS Docker container is running:

```bash
docker ps --filter "name=canopy-project-repos" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected output:
```
NAMES                  STATUS         PORTS
canopy-project-repos   Up 2 hours     0.0.0.0:5432->5432/tcp
```

If the container is not running, start it:
```bash
docker start canopy-project-repos
```

---

## Step 2 — Verify the Database Has Existing Data (Optional)

Before the simulation, you can show the current state of the database. This makes the "before and after" more visible.

Open a database connection:
```bash
docker exec -it canopy-project-repos psql -U postgres -d canopysense
```

Run this query inside the psql prompt:
```sql
SELECT COUNT(*) AS total_rows FROM canopysense.satellite_data;
```

Note the number shown. After the simulation runs, this number will increase (or stay the same if the same satellite scene is already recorded — the system is designed to never create duplicate entries).

To exit psql:
```sql
\q
```

---

## Step 3 — Open Terminal A: Start the Cloud Function Locally

Navigate to the project root:
```bash
cd /home/dikoharyadhanto/Documents/Works/Projects/002_CanopySense
```

Load the GEE credentials and start the local Cloud Function server:
```bash
set -a && source 04_Test/.env && set +a && \
LOCAL_REGISTRY_JSON=$(cat 04_Test/test_registry.json) \
functions-framework --target=patcher_cloud \
  --source=03_Build/patcher_cloud_function.py \
  --port=8080
```

When it is ready, you will see:
```
Serving function...
Function: patcher_cloud
URL: http://localhost:8080/
```

**Leave Terminal A open.** The server is now listening for requests.

---

## Step 4 — Open Terminal B: Run the Trigger Script

Open a **second** terminal window. Navigate to the same project root:
```bash
cd /home/dikoharyadhanto/Documents/Works/Projects/002_CanopySense
```

Point Patcher-Local to the local Cloud Function (instead of the live cloud URL), then run it:
```bash
set -a && source 04_Test/.env && set +a && \
CLOUD_FUNCTION_URL=http://localhost:8080 \
python3 03_Build/patcher_local.py
```

---

## Step 5 — Watch It Run

Terminal B will show the progress of the trigger script in real time:

```
08:30:01 [INFO] — Calling Cloud Function: http://localhost:8080 (contractor: CONTRACTOR_TEST)
08:30:48 [INFO] — Received 5 record(s) from Cloud Function.
08:30:48 [INFO] — Inserted 5 row(s) to satellite_data (ON CONFLICT DO NOTHING).
08:30:48 [INFO] — Patcher-Local complete. Rows inserted to satellite_data: 5
```

Meanwhile, Terminal A shows the Cloud Function processing the request in the background — GEE authentication, satellite scene selection, cloud masking, index calculation, and data extraction are all happening there.

The whole run takes **roughly 1–3 minutes** depending on network speed to Google Earth Engine.

---

## Step 6 — View the Results in the Database

After the run completes, open a database connection to see the inserted data:

```bash
docker exec -it canopy-project-repos psql -U postgres -d canopysense
```

**Query 1: Count all records**
```sql
SELECT COUNT(*) AS total_rows FROM canopysense.satellite_data;
```

This confirms data was written. Compare to the count from Step 2.

---

**Query 2: Show the most recent satellite records**
```sql
SELECT
    block_id,
    acquisition_date,
    sensor,
    ROUND(ndvi::numeric, 4)        AS ndvi,
    ROUND(evi::numeric, 4)         AS evi,
    ROUND(cloud_cover::numeric, 2) AS cloud_cover_pct
FROM canopysense.satellite_data
ORDER BY acquisition_date DESC, block_id ASC
LIMIT 10;
```

Expected output (your dates and values will vary based on the actual satellite scene selected):
```
 block_id | acquisition_date |  sensor   |  ndvi  |  evi   | cloud_cover_pct
----------+------------------+-----------+--------+--------+-----------------
       18 | 2026-04-16       | sentinel-2 | 0.6124 | 0.3891 |            3.20
       21 | 2026-04-16       | sentinel-2 | 0.5834 | 0.3612 |            4.10
       24 | 2026-04-16       | sentinel-2 | 0.6441 | 0.4021 |            2.80
       25 | 2026-04-16       | sentinel-2 | 0.5512 | 0.3287 |            5.60
       29 | 2026-04-16       | sentinel-2 | 0.6038 | 0.3754 |            3.90
(5 rows)
```

---

**Query 3: Show the full record for one block**
```sql
SELECT *
FROM canopysense.satellite_data
WHERE block_id = 18
ORDER BY acquisition_date DESC
LIMIT 1;
```

This shows all vegetation indices for a single block — NDVI, EVI, NDRE (Sentinel-2 only), SAVI, GNDVI, cloud cover, and the quality metadata stored in the `features` column.

---

**Query 4: Summary by sensor and date**
```sql
SELECT
    acquisition_date,
    sensor,
    COUNT(*)                            AS blocks_processed,
    ROUND(AVG(ndvi)::numeric, 4)        AS avg_ndvi,
    ROUND(AVG(cloud_cover)::numeric, 2) AS avg_cloud_cover_pct
FROM canopysense.satellite_data
GROUP BY acquisition_date, sensor
ORDER BY acquisition_date DESC;
```

This gives a high-level view of what was captured per satellite pass.

---

## Step 7 — Stop the Local Cloud Function

When the demo is complete, go back to Terminal A and press `Ctrl + C` to stop the local server.

---

## What the Results Mean

| Column | What It Tells You |
|--------|------------------|
| `block_id` | Which plantation block this measurement belongs to |
| `acquisition_date` | The date the satellite captured this image |
| `sensor` | Which satellite was used (`sentinel-2`, `landsat-8`, or `landsat-9`) |
| `ndvi` | Normalized Difference Vegetation Index — higher = healthier vegetation (0.5–0.8 is typical for healthy palm) |
| `evi` | Enhanced Vegetation Index — similar to NDVI but better in dense canopy areas |
| `ndre` | Red Edge index — Sentinel-2 only — sensitive to early stress before it's visible in NDVI |
| `savi` | Soil-Adjusted Vegetation Index — corrects for bare soil influence |
| `gndvi` | Green NDVI — sensitive to chlorophyll content |
| `cloud_cover` | Percentage of the block obscured by cloud in this image |
| `features` | JSON metadata: valid pixel ratio and quality flag |

---

## How Duplicate Protection Works

If you run the trigger script a second time with the same satellite scene still being the most recent available, you will see:

```
[INFO] — Received 5 record(s) from Cloud Function.
[INFO] — Inserted 0 row(s) to satellite_data (ON CONFLICT DO NOTHING).
[INFO] — Patcher-Local complete. Rows inserted to satellite_data: 0
```

**This is correct behavior.** The system never creates duplicate records for the same block + date + sensor combination. Running the script multiple times is always safe.

---

## Troubleshooting the Demo

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Terminal A shows `Address already in use` | Port 8080 is already occupied | Run `lsof -i :8080` to find and stop the process |
| Terminal B shows `403 Forbidden` | Wrong API key in `.env` | Ensure `PATCHER_API_KEY=my-test-key-123` in `.env` |
| Terminal B shows `Connection refused` | Terminal A not started yet | Start Terminal A first, wait for "Serving function..." message |
| Terminal B shows `PostGIS ingestion failed` | Docker container not running | Run `docker start canopy-project-repos` |
| Run takes more than 5 minutes | GEE is slow to respond | Wait — GEE processing time varies. Normal range is 1–5 minutes |

---

## Relationship to the Production Setup

In the production environment, the simulation maps directly to real components:

| Simulation Component | Production Equivalent |
|---------------------|-----------------------|
| `functions-framework` local server | Google Cloud Function (`patcher_cloud`) |
| `test_registry.json` (local file) | Google Secret Manager (`canopysense-api-key-registry`) |
| `localhost:5432` PostGIS | Contractor's production PostGIS server |
| Same `patcher_local.py` script | Same script — no changes needed for production |

The contractor only changes the `.env` file — `CLOUD_FUNCTION_URL` points to the real Cloud Function URL instead of `localhost:8080`, and the PostGIS settings point to their production database.

---

---

## Docker-Based Integration Testing (04_Test/)

A separate, isolated test environment is available in `04_Test/`. Unlike the functions-framework simulation above, this environment does not require `gcloud` authentication, GEE credentials, or a real cloud deployment. It is the standard method for running integration tests during development.

**What it runs:**
- Docker Compose brings up a PostGIS container pre-seeded with test blocks and schema
- `mock_cloud.py` (stdlib-only) stands in for the Cloud Function — returns a valid `writes` response without touching GEE
- `patcher_local.py` runs inside a container and writes results to the Docker PostGIS

**Prerequisite:** copy `04_Test/.env.test.example` to `04_Test/.env.test` and fill in the values (no GEE credentials needed — the mock handles all responses).

**Start the environment:**
```bash
cd /home/dikoharyadhanto/Documents/Works/Projects/002_CanopySense
docker compose -f 04_Test/docker-compose.yml up --build
```

**Run mock cloud in a separate terminal:**
```bash
cd /home/dikoharyadhanto/Documents/Works/Projects/002_CanopySense
python3 04_Test/mock_cloud.py
```

**Verify results in the Docker PostGIS:**
```bash
docker compose -f 04_Test/docker-compose.yml exec postgis \
  psql -U patcher -d canopysense_test \
  -c "SELECT block_id, acquisition_date, sensor FROM canopysense.satellite_data"
```

**When to use each simulation:**

| Use Case | Method |
|----------|--------|
| Show the full pipeline with real satellite data to stakeholders | functions-framework (this guide) |
| Run integration tests during development — no GEE needed | Docker (`04_Test/`) |
| Verify a specific bug fix against realistic PostGIS state | Docker (`04_Test/`) |
| Test Cloud Function response contract changes | Docker (`04_Test/` + mock_cloud.py) |

---

*CanopySense LOCAL_SIMULATION.md — v1.1 — 2026-04-25*
