# CanopySense — Real Scenario Workflow

**Purpose:** Explain how the full CanopySense system works when integrated with a contractor's real production PostGIS server.
**Audience:** Project team, contractors, stakeholders
**Last Updated:** 2026-04-20

---

## What This Document Covers

This document describes the production workflow — the real thing, not a simulation. The contractor has their own server with PostGIS running, the administrator has issued them an API key, and the entire pipeline runs across real infrastructure.

By the end of a successful run, processed satellite vegetation data will be stored in the contractor's own database — ready for their reporting, dashboards, or analysis tools.

The full production chain looks like this:

```
Contractor's Server                  Google Cloud                    External
──────────────────    ────────────────────────────────────────    ────────────
                      │                                          │
  [patcher_local.py]  →  [Cloud Function: patcher_cloud]  →  [Google Earth Engine]
        ↑                         │                                  │
        │              [Secret Manager]                              │
        │              ├── API key registry  (validate contractor)  │
        │              └── GEE service account key  (fetch & use) ──┘
        │                         │
        └─── JSON response ───────┘
        ↓
  [Contractor's PostGIS]
──────────────────────
```

Everything on the left (contractor's server and PostGIS) belongs to the contractor. Everything in the middle (Cloud Function, Secret Manager) belongs to the administrator. Google Earth Engine is the satellite data source.

---

## How It Is Different from the Local Simulation

| Aspect | Local Simulation | Real Production |
|--------|-----------------|-----------------|
| Cloud Function | Runs on laptop via `functions-framework` | Runs in Google Cloud (always on) |
| API key registry | Loaded from `test_registry.json` on laptop | Fetched from Google Cloud Secret Manager |
| GEE credentials | Fetched via laptop's `gcloud` login | Fetched via Cloud Function's service account (automatic) |
| PostGIS database | Docker container on laptop | Contractor's real server |
| Bore tunnel | Needed (to expose local DB to cloud) | Not needed (contractor's server is directly reachable) |
| `functions-framework` | Required | Not required |
| `gcloud` login on contractor's machine | Required | Not required |

In production, the contractor does not need any Google account, any Google Cloud tools, or any special setup beyond Python and PostgreSQL.

---

## Prerequisites

Before the first real run can happen, both sides need to be ready.

### Administrator Side (One-Time Setup — Already Done)

| Item | Status |
|------|--------|
| Cloud Function `patcher_cloud` deployed to Google Cloud | Done |
| GEE service account key stored in Secret Manager | Done |
| API key registry (`canopysense-api-key-registry`) created in Secret Manager | Done |
| IAM roles granted to Cloud Function's service account | Done |

### Contractor Side (Per-Contractor Setup)

| Item | Who Does It | Notes |
|------|------------|-------|
| PostgreSQL 12+ with PostGIS installed and running | Contractor | Must be accessible from their server |
| `canopysense` schema and tables created (DDL script applied) | Contractor | Admin provides the DDL script |
| `patcher_local.py` copied to their server | Contractor | Provided by admin |
| `.env` file configured with their credentials | Contractor | See Section A.2 of GUIDANCE.md |
| Python 3.8+ installed with required packages | Contractor | `pip install requests python-dotenv psycopg2-binary` |
| API key issued and added to Secret Manager registry | Administrator | See GUIDANCE.md Section A.0 |
| Read-only audit user (`canopysense_audit`) created in their DB | Contractor | Admin uses this to verify data independently |

---

## Step-by-Step: What Happens During a Real Run

### Step 1 — Contractor Triggers the Script

The contractor runs one command on their server:

```bash
cd /path/to/patcher
python3 patcher_local.py
```

Or, if set up on a schedule (cron), this happens automatically — the contractor does not need to do anything.

---

### Step 2 — Patcher-Local Sends a Request to the Cloud

`patcher_local.py` reads the configuration from `.env` and sends a secure HTTPS request to the Cloud Function:

```
POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud
Headers:
  X-API-Key: <contractor's API key>
  Content-Type: application/json
```

The contractor's API key travels encrypted over HTTPS — it is never exposed in plain text.

---

### Step 3 — Cloud Function Validates the Request

The Cloud Function receives the request and immediately checks two things:

**Check 1 — Is the API key present?**
If no key was sent in the header → returns `401 Unauthorized`. The run stops here.

**Check 2 — Is the API key valid and active?**
The Cloud Function fetches the API key registry from Secret Manager and looks up the key's SHA-256 hash. Three outcomes:
- Key not found → `403 Forbidden: Invalid API Key`
- Key found but status is `REVOKED` → `403 Forbidden: API Key revoked`
- Key found and status is `ACTIVE` → proceeds to Step 4

This entire validation step takes less than one second. Nothing in the core engine has been touched yet.

---

### Step 4 — Cloud Function Fetches GEE Credentials

Once the contractor is authenticated, the Cloud Function retrieves the Google Earth Engine service account key from Secret Manager. This key allows the system to connect to GEE and request satellite imagery processing.

The contractor never sees this key. It exists only inside Google Cloud and is loaded into memory for the duration of this request only.

---

### Step 5 — Core Engine Runs

With GEE credentials ready, the core engine executes the full satellite data pipeline:

1. Loads all plantation blocks from the database definition
2. Calculates the date window (last 7 days)
3. Searches for the best available satellite scene (Sentinel-2 preferred, Landsat fallback)
4. Applies cloud masking to remove obscured pixels
5. Calculates vegetation indices: NDVI, EVI, NDRE, SAVI, GNDVI
6. Extracts per-block statistics using Google Earth Engine's compute infrastructure
7. Applies quality filtering (blocks with too much cloud cover are skipped)
8. Packages the results as a structured data record

This is the longest step — typically **2–5 minutes** depending on the number of blocks and satellite scene complexity.

---

### Step 6 — Results Are Returned to the Contractor

The Cloud Function sends the processed records back to `patcher_local.py` as a JSON response:

```json
{
  "status": "success",
  "api_version": "1.1",
  "timestamp": "2026-04-20T10:30:05Z",
  "contractor_id": "CONTRACTOR_ACME_FARMS",
  "errors": [],
  "writes": [
    {
      "table": "satellite_data",
      "rows": [
        {
          "block_id": "18",
          "acquisition_date": "2026-04-18",
          "sensor": "sentinel-2",
          "ndvi": "0.6124",
          "evi": "0.3891",
          ...
        },
        ...
      ]
    }
  ]
}
```

The data travels back to the contractor's server over the same encrypted HTTPS connection.

---

### Step 7 — Patcher-Local Writes to the Contractor's PostGIS

`patcher_local.py` receives the JSON, parses each record, and inserts it into the contractor's local `canopysense.satellite_data` table using their own database credentials from `.env`.

The script is designed to be **safe to run multiple times** — if a record for the same block, date, and sensor already exists, it is silently skipped. No duplicates are ever created.

The contractor's terminal shows:
```
10:30:01 [INFO] — Calling Cloud Function: https://... (contractor: CONTRACTOR_ACME_FARMS)
10:32:18 [INFO] — Received 84 record(s) from Cloud Function.
10:32:18 [INFO] — Inserted 84 row(s) to satellite_data (ON CONFLICT DO NOTHING).
10:32:18 [INFO] — Patcher-Local complete. Rows inserted to satellite_data: 84
```

---

### Step 8 — Everything Is Logged

Every step of the process is recorded in Google Cloud Logging under the administrator's account. The contractor does not need to manage any logs on their side — but the administrator has a full audit trail:

```json
{ "audit": true, "contractor_id": "CONTRACTOR_ACME_FARMS", "status": "AUTH_OK",  "detail": "Triggering core engine" }
{ "audit": true, "contractor_id": "CONTRACTOR_ACME_FARMS", "status": "SUCCESS",  "detail": "rows=84" }
```

---

## Verifying the Results

### Contractor's View — Check Their Own Database

The contractor connects to their PostGIS and runs:

```sql
-- Confirm data arrived
SELECT COUNT(*) AS total_rows FROM canopysense.satellite_data;

-- See the most recent records
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

---

### Administrator's View — Verify via Cloud Logging

Log into [console.cloud.google.com](https://console.cloud.google.com) → project **canopysense** → **Logging → Log Explorer** and filter:

```
resource.type="cloud_run_revision"
resource.labels.service_name="patcher-cloud"
jsonPayload.audit=true
jsonPayload.contractor_id="CONTRACTOR_ACME_FARMS"
```

Confirm the `AUTH_OK` and `SUCCESS` entries with the expected `rows=` count.

---

### Administrator's View — Verify Directly in Contractor's Database

Using the read-only audit credentials provided by the contractor (see GUIDANCE.md Step 8), connect directly:

```bash
psql -h <contractor_db_host> -p 5432 -U canopysense_audit -d canopysense
```

Then run:

```sql
-- Confirm total data volume
SELECT COUNT(*) AS total_rows FROM canopysense.satellite_data;

-- Confirm latest acquisition is recent
SELECT MAX(acquisition_date) AS latest_data FROM canopysense.satellite_data;

-- Summary by date and sensor
SELECT
    acquisition_date,
    sensor,
    COUNT(*)                            AS blocks_processed,
    ROUND(AVG(ndvi)::numeric, 4)        AS avg_ndvi,
    ROUND(AVG(cloud_cover)::numeric, 2) AS avg_cloud_pct
FROM canopysense.satellite_data
GROUP BY acquisition_date, sensor
ORDER BY acquisition_date DESC;
```

This gives the administrator full visibility into the contractor's data without any write access to their server.

---

## What Each Party Is Responsible For

| Responsibility | Contractor | Administrator |
|---------------|-----------|---------------|
| Running `patcher_local.py` | ✅ | |
| Maintaining their PostGIS server | ✅ | |
| Keeping their `.env` file secure | ✅ | |
| Reporting failures to admin | ✅ | |
| Issuing and revoking API keys | | ✅ |
| Maintaining the Cloud Function | | ✅ |
| Monitoring Cloud Logging | | ✅ |
| Verifying data via read-only access | | ✅ |
| Managing GEE credentials | | ✅ |

---

## What Happens If Something Goes Wrong

| Symptom | Likely Cause | Who Acts |
|---------|-------------|----------|
| Contractor gets `401 Unauthorized` | API key missing from `.env` | Contractor checks their `.env` |
| Contractor gets `403 Forbidden: Invalid API Key` | Wrong key or typo in `.env` | Contractor re-copies key from secure delivery |
| Contractor gets `403 Forbidden: API Key revoked` | Key was revoked by admin | Contractor contacts administrator |
| Contractor gets `504 Gateway Timeout` | Core engine took too long | Admin checks Cloud Logging; contractor increases `FUNCTION_TIMEOUT_SECONDS` |
| Contractor gets `500 Internal Server Error` | Server-side failure | Admin checks Cloud Logging for `ENGINE_ERROR` entry |
| `Inserted 0 rows` after a successful run | Same scene already in DB (no new data this week) | Expected behavior — not an error |
| Admin sees `rows=84` in logs but DB shows 0 | Contractor's PostGIS write failed | Contractor checks their DB connection and disk space |

---

## Key Differences from the Local Simulation at a Glance

The local simulation was used to prove the system works before any real server was involved. In real production:

- No `functions-framework` — the Cloud Function is always running in Google Cloud
- No `test_registry.json` — API keys are validated directly from Secret Manager
- No bore tunnel — the contractor's PostGIS is on a real server with a real IP
- No `gcloud` login on contractor's machine — the contractor only needs Python
- The admin verifies results via Cloud Logging **and** direct read-only DB access

Everything else — the API key, the request format, the GEE pipeline, the data schema, the SQL queries — is identical to what was demonstrated in the local simulation.

---

## Architectural Decision: How the Cloud Function Gets Block Polygons

This section addresses an important question that comes up when moving from local simulation to real production:

> **`patcher_local.py` only sends an API key to the Cloud Function. It sends no block data. So how does the Cloud Function know which plantation areas to process?**

The Cloud Function must connect to a database to read the block polygon geometries before it can ask Google Earth Engine to process anything. In local simulation, we temporarily exposed the local Docker PostGIS to the Cloud Function via a bore tunnel — that was a testing workaround, not a production design.

For real production, there are three architectural options. Each has a different answer to the question: **whose database does the Cloud Function connect to?**

---

### Option A — Central Blocks Database (Admin-Managed in Google Cloud)

**How it works:**

The administrator maintains one central PostGIS database running inside Google Cloud (e.g., Cloud SQL). All contractor block polygons are stored in this central database, uploaded once during onboarding. The Cloud Function always reads block data from there — it never needs to connect to the contractor's server at all.

The contractor's own PostGIS remains a write-only destination: it only ever receives processed satellite results from `patcher_local.py`. Nothing flows outward from it to the cloud.

```
Contractor's Server                    Google Cloud
────────────────────    ───────────────────────────────────────────────
                        │                                             │
  [patcher_local.py] → [Cloud Function]  →  [Google Earth Engine]   │
        ↑                    ↓                                        │
        │            reads blocks from                                │
        │            [Central PostGIS]  ──────────────────────────── ┘
        │            (admin-managed,
        │             inside Google Cloud)
        │                    │
        └── receives results ┘
        ↓
  [Contractor's PostGIS]
  (write-only, never exposed to cloud)
────────────────────
```

**Process:**
1. During onboarding, admin uploads the contractor's block shapefile to the central PostGIS once
2. Contractor runs `patcher_local.py` → sends only the API key
3. Cloud Function reads blocks from the central PostGIS
4. GEE processes those blocks
5. Results returned to `patcher_local.py` → written to contractor's local PostGIS

**Benefits:**
- Contractor's database is completely private — no ports opened, no firewall changes needed
- Admin has full control over which blocks are processed for each contractor
- Block data is stored in one place — easy to update, audit, and version
- No dependency on the contractor's network or server availability during processing
- Most secure architecture of the three options

**Risks:**
- Admin must maintain a separate Cloud SQL instance (additional monthly cost ~$30–80/month depending on size)
- If admin uploads wrong block data during onboarding, results will be wrong — no automatic validation against contractor's own DB
- Block updates (new plantation areas, retired blocks) must go through the admin — contractor cannot self-serve

**Best for:** Projects with many contractors, stable block boundaries, and an admin who wants full control over what gets processed.

---

### Option B — Patcher-Local Sends Blocks in the Request

**How it works:**

`patcher_local.py` is given a slightly expanded role: before calling the Cloud Function, it reads the block polygon geometries from the contractor's own local PostGIS and includes them in the HTTP request body. The Cloud Function receives both the API key and the block data in one request — it never needs to connect to any database to get polygons.

The Cloud Function processes only the blocks it received in the request, runs GEE, and returns results. Everything stays in one round trip.

```
Contractor's Server                           Google Cloud
────────────────────────────    ────────────────────────────────────
                                │                                   │
  [Contractor's PostGIS]        │                                   │
        ↓ (reads blocks)        │                                   │
  [patcher_local.py]  →  POST (API key + block polygons as JSON)   │
        ↑                  → [Cloud Function]  →  [Google Earth Engine]
        └──── receives results ─────────────── ←
        ↓
  [Contractor's PostGIS]
  (writes results back)
────────────────────────────
```

**Process:**
1. Contractor runs `patcher_local.py`
2. Script reads blocks from contractor's local PostGIS first
3. Script sends API key + block GeoJSON to Cloud Function in one request
4. Cloud Function validates key, processes the received blocks via GEE
5. Results returned to `patcher_local.py` → written back to contractor's PostGIS

**Benefits:**
- No central database needed — no additional cloud infrastructure cost
- Contractor's block data stays on their own server
- Block updates are instant — contractor updates their own DB, next run uses new blocks automatically
- Contractor is self-sufficient — no admin dependency for block management
- No outbound connection from cloud to contractor's server

**Risks:**
- `patcher_local.py` needs code changes — currently it sends no block data
- Large plantation areas with many blocks means larger HTTP request payloads
- If the contractor's PostGIS is empty or blocks table is wrong, GEE has nothing to process — harder to diagnose from admin side
- Admin has less visibility into what blocks were actually processed

**Best for:** Projects where contractors manage their own block boundaries and need to update them independently without going through the admin.

---

### Option C — Contractor Exposes Their Database to the Cloud Function

**How it works:**

The Cloud Function connects directly to the contractor's PostGIS server over the internet to read block data — the same way it did during Level 2 testing via the bore tunnel. In production, the tunnel is replaced by a real database connection: the contractor opens a specific port on their server's firewall and the Cloud Function connects using credentials stored in its environment variables.

```
Contractor's Server                           Google Cloud
────────────────────────    ────────────────────────────────────────
                            │                                       │
  [Contractor's PostGIS] ←──┼── DB connection (reads blocks) ──── [Cloud Function]
        ↓                   │                                    ↓
  (blocks read by cloud)    │                          [Google Earth Engine]
        ↓                   │                                    ↓
  [Contractor's PostGIS] ←──┼───── receives results ─────────────
  (results written back)    │
────────────────────────    │
```

**Process:**
1. Contractor configures their server firewall to allow inbound connections from Google Cloud's IP range on port 5432
2. Admin stores contractor's DB credentials (host, port, user, password) in Cloud Function environment variables
3. Contractor runs `patcher_local.py` → sends only the API key
4. Cloud Function connects directly to contractor's PostGIS, reads blocks
5. GEE processes those blocks, results returned to Cloud Function
6. Cloud Function returns results to `patcher_local.py` → written to same PostGIS

**Benefits:**
- No code changes needed — this is how the system currently works (bore tunnel was simulating this)
- No central database to maintain
- Block updates on contractor's side are immediately available to the cloud

**Risks:**
- Contractor must open their database port to the internet — significant security risk
- PostgreSQL exposed to public internet is a common attack vector even with a strong password
- Admin holds the contractor's database credentials — a sensitive trust boundary
- If contractor's server goes down or network is slow, the Cloud Function cannot read blocks and the entire run fails
- Firewall rules and IP allowlisting for Google Cloud IP ranges are complex and change over time (Google Cloud publishes IP ranges but they are large and update periodically)
- Not recommended for production unless inside a VPN or private network

**Best for:** Internal testing only, or architectures where both the Cloud Function and the contractor's database are inside the same private network (VPN). Not suitable for internet-facing production deployments.

---

## Comparison Summary

| | Option A — Central DB | Option B — Send Blocks in Request | Option C — Expose Contractor DB |
|---|---|---|---|
| **Contractor's DB exposed to cloud** | No | No | Yes |
| **Code changes needed** | No | Yes (`patcher_local.py`) | No |
| **Additional infrastructure cost** | Yes (Cloud SQL) | No | No |
| **Block updates self-served by contractor** | No (goes through admin) | Yes | Yes |
| **Admin control over what gets processed** | Full | Partial | Partial |
| **Works if contractor's server is down** | Yes | No | No |
| **Security risk** | Low | Low | High |
| **Recommended for production** | ✅ Yes | ✅ Yes | ❌ Testing only |

---

## Current Status

The current implementation (as of v0.10) uses **Option B** — Patcher-Local reads block geometries from the contractor's local PostGIS and sends them in the POST request body. The Cloud Function has zero outbound database connections. See the section below for the full reasoning.

**Option B is implemented and active.** No further code changes are required for the block delivery mechanism.

---

## Decision: Option B — Why and How

### Why Option B Was Chosen

After discussion, Option B (Patcher-Local sends blocks in the request) was selected for the following reasons:

**1. Scheduled runs give sufficient time for retry**
The pipeline runs on a schedule — weekly or daily. If a request fails midway, there is no urgency to recover in milliseconds. A clean retry within the same scheduled window is acceptable. This makes the added complexity of retry logic manageable rather than critical.

**2. GeoJSON payload size is not a concern**
A plantation block polygon is a small geometry — even estates with hundreds of blocks produce a GeoJSON payload in the range of 50–500 KB. This is well within HTTP request limits and adds negligible overhead to the network call.

**3. Schema validation is handled by read-only audit access**
The administrator holds read-only access (`canopysense_audit`) to the contractor's PostGIS. Before going live, the admin connects and verifies that the contractor's block structure matches the expected schema. This is a one-time check, not an ongoing dependency.

**4. Data-parser standardizes uploads on contractor's side**
Every time a contractor uploads a shapefile through their application, a data-parser script standardizes the geometry and attribute format before writing to PostGIS. This ensures the blocks sent to the Cloud Function are always in the correct structure — no runtime format surprises.

**5. No extra cloud infrastructure cost**
Option A requires a Cloud SQL instance running permanently. Option B requires nothing additional in the cloud — the Cloud Function simply accepts the blocks from the request body.

---

### What Changed in the Code for Option B

The following changes were made in v0.9 compared to the v0.7 implementation. These are complete.

**`patcher_local.py` — expanded to read and send blocks:**
- Before calling the Cloud Function, connect to contractor's local PostGIS
- Query `canopysense.blocks` table — read `block_id`, `code`, `name`, and `geometry` (as GeoJSON)
- Serialize the result as a GeoJSON FeatureCollection
- Include it in the POST request body alongside the API key header

**`patcher_cloud_function.py` — accept blocks from request body:**
- Parse the GeoJSON FeatureCollection from the request body
- Pass it to `engine_launcher` instead of having the engine read from a database
- Remove the `PGHOST`/`PGPORT`/`PGDATABASE` environment variables from the Cloud Function — the Cloud Function no longer needs any database connection

**`engine_launcher.py` — accept blocks as parameter:**
- `run_pipeline()` receives a pre-loaded GeoDataFrame (blocks) as a parameter instead of calling `_load_blocks_from_db()`
- The DB connection inside the engine is no longer needed for block loading

**What does NOT change:**
- API key validation flow — identical
- GEE processing logic — identical
- Results returned as JSON to `patcher_local.py` — identical
- `patcher_local.py` writing results to contractor's PostGIS — identical
- Schema of `canopysense.satellite_data` — identical

---

### Updated Architecture Diagram (Option B)

```
Contractor's Server                              Google Cloud
──────────────────────────────    ──────────────────────────────────────────
                                  │                                         │
  [Contractor's PostGIS]          │                                         │
    canopysense.blocks            │                                         │
        ↓ Step 1: read blocks     │                                         │
  [patcher_local.py]              │                                         │
        ↓ Step 2: POST request    │                                         │
        ──── API key + GeoJSON ──→ [Cloud Function: patcher_cloud]          │
                                       ↓ validate key (Secret Manager)      │
                                       ↓ load GeoJSON from request body     │
                                       ↓ fetch GEE credentials (Secret Mgr) │
                                       ↓ run GEE pipeline ──────────────→ [Google Earth Engine]
                                       ↓ receive results ←──────────────
                                       ↓ return JSON response
        ←── results JSON ─────────────
        ↓ Step 3: write results
  [Contractor's PostGIS]
    canopysense.satellite_data
──────────────────────────────
```

The Cloud Function now has zero outbound database connections. It only reads from Secret Manager (inbound) and calls Google Earth Engine.

---

## Scenario 4: Real-Time Upload Trigger (New User Flow)

The three scenarios above assume the pipeline runs on a schedule or is triggered manually by the contractor. There is a fourth scenario that requires different handling:

> **A new contractor user creates an account, uploads a shapefile through the application's upload feature, and expects the satellite data pipeline to run immediately — not wait for the next scheduled cycle.**

This is an event-driven trigger, not a scheduled one. The user is actively waiting for results. The retry strategy must be different.

---

### How the Real-Time Flow Works

```
User Action                    Contractor's Server              Google Cloud
───────────────    ────────────────────────────────    ──────────────────────
                   │                                  │
  [Upload SHP] →  [Data-Parser]                       │
                       ↓ standardize geometry          │
                       ↓ write to canopysense.blocks   │
                   [PostGIS]                           │
                       ↓ trigger event                 │
                   [patcher_local.py]                  │
                       ↓ read blocks                   │
                       ──── POST (API key + GeoJSON) → [Cloud Function]
                       ←── results JSON ───────────────
                       ↓ write to satellite_data
                   [PostGIS]
                       ↓
                   [App notifies user: data is ready]
───────────────────────────────────────────────────────
```

**Key difference from scheduled runs:**
In a scheduled run, a failure means "try again next week." In a real-time upload trigger, a failure means "the user is staring at a loading screen." Retry logic must be faster, smarter, and visible to the user.

---

### Retry Loop Design for Real-Time Trigger

The retry loop must handle three categories of failure differently:

**Category 1 — Transient failures (safe to retry immediately)**
These are temporary problems that usually resolve within seconds or minutes:
- Network timeout between contractor's server and Cloud Function
- Google Earth Engine temporary unavailability
- Cloud Function cold start delay

Retry strategy: **exponential backoff**
```
Attempt 1 → wait 30 seconds → Attempt 2 → wait 60 seconds → Attempt 3 → wait 120 seconds → give up
```

Total retry window: ~3.5 minutes before declaring failure. Acceptable for a user upload flow.

**Category 2 — Deterministic failures (do NOT retry — fix first)**
These will fail every time regardless of how many retries are attempted:
- `403 Forbidden` — invalid or revoked API key
- `401 Unauthorized` — API key missing from `.env`
- Empty blocks table — data-parser failed to write blocks
- Schema mismatch — contractor's DB structure does not match expected format

Retry strategy: **fail immediately, notify the user with a specific error message.** Retrying these wastes time and confuses the user.

**Category 3 — Partial failures (idempotent retry is safe)**
- Cloud Function returned results but `patcher_local.py` failed to write to PostGIS mid-way
- Some blocks written, some not

Retry strategy: **retry the full request safely.** Because writes use `ON CONFLICT DO NOTHING`, already-written blocks are skipped automatically. No duplicates are created. The retry picks up where it left off effectively.

---

### Retry Loop Behaviour Table

| Failure Type | HTTP Code | Retry? | Wait Before Retry | Max Attempts | User Message |
|-------------|-----------|--------|-------------------|-------------|-------------|
| Network timeout | — | Yes | 30s, 60s, 120s | 3 | "Processing — retrying..." |
| GEE unavailable | 500 | Yes | 60s, 120s | 2 | "Satellite service busy — retrying..." |
| Invalid API key | 403 | No | — | 0 | "Access denied — contact administrator" |
| Revoked API key | 403 | No | — | 0 | "Access revoked — contact administrator" |
| Missing API key | 401 | No | — | 0 | "Configuration error — contact administrator" |
| PostGIS write failed | — | Yes | 10s | 2 | "Saving data — retrying..." |
| All retries exhausted | — | No | — | — | "Processing failed — queued for next scheduled run" |

---

### What Happens When All Retries Are Exhausted

The failed job should not be silently dropped. Two things must happen:

**1. The user is notified**
The application shows a clear message explaining the run did not complete and will be retried automatically on the next scheduled cycle. The user should not need to re-upload their file.

**2. The job is queued for the next scheduled run**
The data-parser already wrote the blocks to PostGIS during upload. The next scheduled run of `patcher_local.py` will automatically pick up those blocks and process them. No data is lost — only the immediate result is delayed.

This means the real-time trigger is effectively a "best effort fast path." If it succeeds, the user gets results immediately. If it fails completely, the scheduled run serves as the guaranteed fallback — the user just waits a bit longer.

---

### What the Data-Parser Must Guarantee

For Option B to work reliably in the real-time scenario, the data-parser (the component that standardizes shapefile uploads) must guarantee the following before triggering `patcher_local.py`:

| Guarantee | Why It Matters |
|-----------|---------------|
| All geometries are valid polygons in EPSG:4326 | GEE rejects invalid or non-WGS84 geometries |
| `block_id` is unique per record | Duplicate IDs produce duplicate results |
| `geometry` column is not null for any row | Null geometries cause GEE to fail silently |
| `canopysense.blocks` write is fully committed before trigger fires | `patcher_local.py` must not read a partially-written table |
| Schema matches `canopysense.blocks` DDL exactly | Mismatched columns cause the pipeline to fail at block-reading step |

The data-parser is the first line of defence. If it guarantees clean data, the pipeline downstream has nothing unexpected to handle.

---

*CanopySense REAL_SCENARIO_WORKFLOW.md — v1.2 — 2026-04-25*
