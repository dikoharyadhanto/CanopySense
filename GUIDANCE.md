# CanopySense Patcher-Local — Operations Guide

**Version:** v0.9 | **Audience:** Operations Staff (no coding knowledge required)
**Last Updated:** 2026-04-21

> This guide covers everything you need to deploy, run, and troubleshoot the CanopySense Patcher-Local system. If you follow the steps exactly, you will not need to contact the development team for normal operations.

---

## Glossary of Terms

| Term                  | Plain English Meaning                                                                                                             |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Patcher-Local**     | A small program on your server that contacts the CanopySense cloud to request satellite data processing                           |
| **Patcher-Cloud**     | The CanopySense processing system running in Google Cloud — you never interact with this directly                                 |
| **Cloud Function**    | A service running in Google Cloud that processes satellite imagery on demand                                                      |
| **API Key**           | A secret password that proves your server is authorized to use the system — unique to your organization                           |
| **PostGIS**           | Your local database where processed satellite results are stored                                                                  |
| **Secret Manager**    | Google's secure vault for storing API keys and configuration secrets                                                              |
| **`.env` file**       | A plain text file on your server that stores your configuration and credentials                                                   |
| **403 Forbidden**     | An error meaning your API key was rejected — either invalid, revoked, or expired                                                  |
| **401 Unauthorized**  | An error meaning no API key was provided in the request                                                                           |
| **Revocation**        | Disabling an API key so it can no longer access the system                                                                        |
| **Cloud Logging**     | Google Cloud's log system — where all CanopySense activity is recorded                                                            |
| **IAM Role**          | A permission in Google Cloud that allows a service to do something (e.g., read secrets)                                           |
| **CONTRACTOR_ID**     | A unique label assigned by the administrator to identify each contractor (e.g., `CONTRACTOR_ACME_FARMS`)                          |
| **API Key Registry**  | A JSON file stored in Secret Manager that lists all contractors, their key hashes, and their status                               |
| **SHA-256 Hash**      | A one-way fingerprint of the API key — the registry stores only this, never the raw key itself                                    |
| **IP Whitelist**      | An optional list of allowed IP addresses for a contractor — requests from other IPs are automatically blocked                     |
| **Onboarding**        | The process of registering a new contractor in the system and issuing them an API key                                             |
| **canopysense_audit** | A read-only PostgreSQL user created on the contractor's server — allows the administrator to verify data without any write access |

---

## Section A: Contractor Onboarding (Administrator Workflow)

This section is for the **CanopySense administrator** — the person who manages API keys and approves contractor access. Contractors do not need to read this section.

---

### A.0 Step 1 — Collect Requirements from the Contractor's Server Developer

Before you can issue an API key, the contractor's server developer must provide the following. Send them this checklist and do not proceed until all items are confirmed.

**Information to request from the contractor:**

| #   | What to Ask For                                    | Why You Need It                                                                                                          | Required? |
| --- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | --------- |
| 1   | **Organization name**                              | Used to create their unique `CONTRACTOR_ID` (e.g., `CONTRACTOR_ACME_FARMS`)                                              | Required  |
| 2   | **Technical contact name + email**                 | For secure API key delivery and incident escalation                                                                      | Required  |
| 3   | **Server operating system**                        | Must be Linux or macOS — Windows is not supported for `patcher_local.py`                                                 | Required  |
| 4   | **Python version installed on server**             | Must be Python 3.8 or newer. Ask them to run `python3 --version`                                                         | Required  |
| 5   | **PostgreSQL version installed**                   | Must be PostgreSQL 12 or newer with PostGIS extension enabled                                                            | Required  |
| 6   | **Confirmation that canopysense schema is set up** | They must run the CanopySense DDL script before any data can be written                                                  | Required  |
| 7   | **Server public IP address or CIDR range**         | Optional but recommended — added as IP whitelist for defense-in-depth                                                    | Optional  |
| 8   | **Preferred run schedule**                         | Weekly? Daily? This determines how they configure their cron job                                                         | Optional  |
| 9   | **Read-only database credentials**                 | Host, port, database name, and a read-only username + password so you can independently verify data was stored correctly | Required  |

> **Note on item 9:** You only need read-only access — not admin access, not write access. The contractor creates a dedicated audit user that can only run `SELECT` queries on the `canopysense.satellite_data` table. This is standard practice in B2B data integrations. See Step 8 below for the exact SQL the contractor needs to run.

---

### A.0 Step 2 — What You Do After Receiving the Information

Once the contractor's server developer has confirmed all required items, complete these steps in order:

**Step 1: Assign a Contractor ID**

Choose a unique identifier for this contractor. Use this format:

```
CONTRACTOR_<ORGANIZATION>_<OPTIONAL_REGION>
```

Examples: `CONTRACTOR_ACME_FARMS`, `CONTRACTOR_BETA_SUMATRA`

---

**Step 2: Generate an API Key**

Run this command in your terminal to generate a secure random key:

```bash
openssl rand -hex 32
```

Example output:

```
a3f8c2d1e9b74f6a2c5d8e1f3b9a7c4d6e2f8a1b3c5d7e9f1a2b4c6d8e0f2a4
```

Copy this value — you will need it for the next two steps.

---

**Step 3: Hash the API Key**

The registry stores only the hash, never the raw key. Generate the SHA-256 hash:

```bash
echo -n "YOUR_API_KEY_HERE" | sha256sum
```

Example:

```bash
echo -n "a3f8c2d1e9b74f6a2c5d8e1f3b9a7c4d6e2f8a1b3c5d7e9f1a2b4c6d8e0f2a4" | sha256sum
```

Copy the hash value (the long string before the space and `-`).

---

**Step 4: Add the Contractor to Secret Manager**

Fetch the current registry, add the new contractor entry, and upload it back:

```bash
# 1. Download current registry to a temp file
~/google-cloud-sdk/bin/gcloud secrets versions access latest \
  --secret=canopysense-api-key-registry \
  --project=canopysense > /tmp/registry.json

# 2. Open /tmp/registry.json in a text editor and add the new entry:
```

Add this block inside the JSON object (alongside existing contractors):

```json
"CONTRACTOR_ACME_FARMS": {
    "api_key_hash": "<paste sha256 hash here>",
    "status": "ACTIVE",
    "issued_date": "<today's date, e.g. 2026-04-20>",
    "ip_whitelist": ["203.0.113.10/32"],
    "last_used": "<today's date>T00:00:00Z"
}
```

If no IP whitelist is needed, set `"ip_whitelist": []`.

```bash
# 3. Upload the updated registry as a new secret version
~/google-cloud-sdk/bin/gcloud secrets versions add canopysense-api-key-registry \
  --data-file=/tmp/registry.json \
  --project=canopysense

# 4. Clean up the temp file
rm /tmp/registry.json
```

---

**Step 5: Verify the New Entry Is Live**

```bash
~/google-cloud-sdk/bin/gcloud secrets versions access latest \
  --secret=canopysense-api-key-registry \
  --project=canopysense | python3 -m json.tool
```

Confirm the new contractor entry appears with `"status": "ACTIVE"`.

---

**Step 6: Send the Contractor Their Access Package**

Deliver the following via a **secure channel** (not plain email — use WhatsApp, Signal, or a shared password manager link):

| Item               | What to Send                                                           |
| ------------------ | ---------------------------------------------------------------------- |
| API Key            | The raw key generated in Step 2 (not the hash)                         |
| Contractor ID      | Their assigned `CONTRACTOR_ID`                                         |
| Cloud Function URL | `https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud` |
| Files              | `patcher_local.py`, `.env.example`, `GUIDANCE.md`                      |

> **Never send the API key and the Contractor ID in the same message.** Send them separately so that intercepting one message is not enough to gain access.

---

**Step 7: Verify Contractor Access (Quick Test)**

After the contractor confirms they have set up their `.env` and run `patcher_local.py`, verify on your side that the call was recorded in Cloud Logging:

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → project **canopysense**
2. Go to **Logging → Log Explorer**
3. Use this filter:
   
   ```
   resource.type="cloud_run_revision"
   resource.labels.service_name="patcher-cloud"
   jsonPayload.audit=true
   jsonPayload.contractor_id="CONTRACTOR_ACME_FARMS"
   ```
4. Confirm you see a `"status": "SUCCESS"` entry with their contractor ID and a `rows=` count

If you see `AUTH_OK` followed by `SUCCESS` — onboarding is complete.

---

**Step 8: Request Read-Only Database Access from the Contractor**

Ask the contractor's server developer to run the following SQL on their PostgreSQL server. This creates a read-only user that you will use to independently verify the data.

**Send them this exact script:**

```sql
-- Run this on the contractor's PostgreSQL server
-- Replace 'choose_a_strong_password' with a real password, then share it with your admin securely

CREATE USER canopysense_audit WITH PASSWORD 'choose_a_strong_password';
GRANT CONNECT ON DATABASE canopysense TO canopysense_audit;
GRANT USAGE ON SCHEMA canopysense TO canopysense_audit;
GRANT SELECT ON canopysense.satellite_data TO canopysense_audit;
```

After running it, they share with you (via secure channel):

| What           | Example                               |
| -------------- | ------------------------------------- |
| DB host / IP   | `192.168.1.100` or `db.acmefarms.com` |
| DB port        | `5432`                                |
| DB name        | `canopysense`                         |
| Audit username | `canopysense_audit`                   |
| Audit password | `choose_a_strong_password`            |

> This user can only read rows from `satellite_data`. It cannot modify, delete, or access any other table. The contractor's operational data outside of CanopySense is completely unaffected.

**Also ask the contractor to ensure their PostgreSQL server accepts connections from your IP address.** They may need to update their `pg_hba.conf` or server firewall to allow your machine to connect.

---

**Step 9: Verify Data Is in the Contractor's Database**

Once you have the read-only credentials, you can connect directly to their PostGIS and confirm the data is there.

**Option A — using psql from terminal:**

```bash
psql -h <contractor_host> -p 5432 -U canopysense_audit -d canopysense
```

Then run:

```sql
-- Count total records stored
SELECT COUNT(*) AS total_rows FROM canopysense.satellite_data;

-- Show the most recent records
SELECT
    block_id,
    acquisition_date,
    sensor,
    ROUND(ndvi::numeric, 4) AS ndvi,
    ROUND(cloud_cover::numeric, 2) AS cloud_cover_pct
FROM canopysense.satellite_data
ORDER BY acquisition_date DESC
LIMIT 10;

-- Confirm data was received from the last run
SELECT MAX(acquisition_date) AS latest_data FROM canopysense.satellite_data;
```

**Option B — using Python from terminal (no psql needed):**

```bash
python3 - <<'EOF'
import psycopg2, os

conn = psycopg2.connect(
    host="<contractor_host>",
    port=5432,
    dbname="canopysense",
    user="canopysense_audit",
    password="<audit_password>"
)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM canopysense.satellite_data;")
print("Total rows:", cur.fetchone()[0])
cur.execute("SELECT MAX(acquisition_date) FROM canopysense.satellite_data;")
print("Latest acquisition date:", cur.fetchone()[0])
conn.close()
EOF
```

Expected output:

```
Total rows: 84
Latest acquisition date: 2026-04-18
```

If `latest acquisition date` is within the last 7 days and the row count is greater than zero, the contractor's pipeline is working correctly.

---

**Onboarding Summary Checklist:**

- [ ] Contractor organization name received
- [ ] Technical contact name + email received
- [ ] Server OS confirmed (Linux/macOS)
- [ ] Python 3.8+ confirmed
- [ ] PostgreSQL 12+ with PostGIS confirmed
- [ ] CanopySense schema setup confirmed by contractor
- [ ] Read-only audit user created by contractor (`canopysense_audit`)
- [ ] Audit DB credentials received (host, port, dbname, user, password)
- [ ] `CONTRACTOR_ID` assigned
- [ ] API key generated (`openssl rand -hex 32`)
- [ ] API key hashed (`sha256sum`)
- [ ] Secret Manager registry updated with new entry
- [ ] Registry verified live (correct entry shows `ACTIVE`)
- [ ] Access package sent via secure channel (API key and CONTRACTOR_ID separately)
- [ ] Contractor confirms first successful run
- [ ] Cloud Logging shows `SUCCESS` entry for their `CONTRACTOR_ID`
- [ ] Admin verified data in contractor's DB using read-only credentials (Step 9)

---

## Section A: Deployment & Setup (Contractor Instructions)

### A.1 What You Need Before Starting

Before deploying Patcher-Local, make sure you have:

- [ ] A server running Linux or macOS with Python 3.8 or newer
- [ ] PostgreSQL/PostGIS installed and running locally
- [ ] The `canopysense.satellite_data` table already created (from Phase 1 setup)
- [ ] Your `CONTRACTOR_ID` and `PATCHER_API_KEY` — provided by your administrator
- [ ] The `CLOUD_FUNCTION_URL` — provided by your administrator

---

### A.2 Step-by-Step: Install Patcher-Local

**Step 1: Get the files**

Copy the following files to your server (provided by your administrator):

```
patcher_local.py
.env.example
```

**Step 2: Install Python dependencies**

Open a terminal and run:

```bash
pip install requests python-dotenv psycopg2-binary
```

Expected output (last line):

```
Successfully installed requests-2.31.0 python-dotenv-1.0.0 psycopg2-binary-2.9.0
```

**Step 3: Create your `.env` configuration file**

```bash
cp .env.example .env
```

Then open `.env` in a text editor and fill in your values:

```
CLOUD_FUNCTION_URL=https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud
CONTRACTOR_ID=YOUR_CONTRACTOR_ID
PATCHER_API_KEY=your_api_key_here
PGHOST=localhost
PGPORT=5432
PGDATABASE=canopysense
PGUSER=canopysense_user
PGPASSWORD=your_secure_password
FUNCTION_TIMEOUT_SECONDS=300
```

> **Important:** The `CLOUD_FUNCTION_URL` above is fixed — do not change it. Replace only `YOUR_CONTRACTOR_ID`, `PATCHER_API_KEY`, and the database credentials with values provided by your administrator.

**Step 4: Verify `.gitignore` (if using git)**

Check that `.env` is listed in your `.gitignore` file. If not, add it:

```bash
echo ".env" >> .gitignore
```

---

### A.3 Required IAM Role Setup (Administrator Task)

> **This step is already completed for the current deployment.** The notes below are for reference if the system is ever redeployed to a new Google Cloud project.

The Cloud Function must have the `roles/secretmanager.secretAccessor` role. Without this, the function cannot read API keys and will return 500 errors.

**Current deployment details (already configured):**

- GCP Project: `canopysense`
- Region: `asia-southeast2`
- Cloud Function service account: `78268232885-compute@developer.gserviceaccount.com`
- Required roles granted: `secretmanager.secretAccessor`, `earthengine.writer`, `serviceusage.serviceUsageConsumer`

**If redeploying to a new project, run:**

```bash
gcloud projects add-iam-policy-binding canopysense \
  --member="serviceAccount:78268232885-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**Verify the role was granted:**

```bash
gcloud projects get-iam-policy canopysense \
  --flatten="bindings[].members" \
  --filter="bindings.role:roles/secretmanager.secretAccessor" \
  --format="table(bindings.members)"
```

Expected output:

```
MEMBERS
serviceAccount:78268232885-compute@developer.gserviceaccount.com
```

---

### A.4 Test Connectivity to Cloud Function

Run this command to verify your server can reach the Cloud Function:

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud \
  -H "Content-Type: application/json"
```

Expected response: `401` (no API key provided — this is correct and means the URL is reachable)

If you see `000` or a connection error, check your network firewall settings.

---

### A.5 Common Setup Mistakes

| Mistake                           | Symptom                                           | Fix                                                                         |
| --------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------- |
| API key has extra spaces          | `403 Forbidden: Invalid API Key`                  | Open `.env`, check there are no spaces around the key value                 |
| Wrong `CLOUD_FUNCTION_URL`        | `ConnectionError` or `404`                        | Copy the exact URL from your administrator's setup email                    |
| `.env` not in the right directory | `Missing required environment variable`           | Run `ls .env` — the file must be in the same folder as `patcher_local.py`   |
| Database not running              | `PostGIS ingestion failed`                        | Run `pg_isready` to check if PostgreSQL is running                          |
| Missing IAM role                  | `500 Internal Server Error: Registry unavailable` | Administrator must grant `roles/secretmanager.secretAccessor` (Section A.3) |

---

## Section B: Normal Operations

### B.1 How to Trigger a Run

Patcher-Local supports two trigger modes:

**Mode 1 — Scheduled Run (all blocks, use for regular/weekly automation):**

```bash
cd /path/to/patcher_local
python3 patcher_local.py
```

This processes all blocks in your database, grouped by afdeling. Each afdeling is one separate batch sent to the Cloud Function. If any batch fails, it is recorded and retried automatically on the next scheduled run — without any action required from you.

**Mode 2 — Upload Trigger (single block, use when a new shapefile is uploaded):**

```bash
cd /path/to/patcher_local
python3 patcher_local.py --block-id 42
```

Replace `42` with the `block_id` of the new block. This processes only that one block immediately, without triggering the full scheduled loop.

**What you will see on a successful scheduled run (example with 2 afdelings):**

```
08:30:01 [INFO]  Run started — mode: scheduled | run_id: a3f8c2d1
08:30:01 [INFO]  Blocks loaded: 41 across 2 batches
08:30:01 [INFO]  Batch 1/2 (afdeling_id=1, 22 blocks, fingerprint=a1b2c3d4) — sending to Cloud Function
08:30:15 [INFO]  Batch 1/2 (afdeling_id=1, ...) — FULL_SUCCESS | rows_inserted=22 | presence_check=22/22 | api_version=1.1
08:30:16 [INFO]  Batch 2/2 (afdeling_id=2, 19 blocks, fingerprint=d4e5f6a7) — sending to Cloud Function
08:30:29 [INFO]  Batch 2/2 (afdeling_id=2, ...) — FULL_SUCCESS | rows_inserted=19 | presence_check=19/19 | api_version=1.1
08:30:29 [INFO]  Run complete — 2/2 FULL_SUCCESS | 0 PARTIAL_SUCCESS | 0 FULL_FAILURE | 0 SKIPPED
```

> **Note:** The first run after a long pause may take 5–10 seconds longer than usual. This is called "cold start" — the Cloud Function is waking up. Subsequent runs in the same hour will be faster.

---

### B.2 How to Verify a Run Succeeded

**Method 1: Check the terminal output**

Look for the final summary line. All batches should show `FULL_SUCCESS`:

```
[INFO]  Run complete — 2/2 FULL_SUCCESS | 0 PARTIAL_SUCCESS | 0 FULL_FAILURE | 0 SKIPPED
```

A `rows_inserted=0` after a successful run is normal — it means the data was already in your database from a previous run.

**Method 2: Query your PostGIS database**

```sql
-- Count total rows in satellite_data
SELECT COUNT(*) FROM canopysense.satellite_data;

-- Show the 5 most recently acquired records
SELECT block_id, acquisition_date, sensor, ndvi
FROM canopysense.satellite_data
ORDER BY acquisition_date DESC
LIMIT 5;
```

If the `acquisition_date` in the most recent rows matches today (or within the last 7 days), the run succeeded.

**Method 3: Check the run log table**

Every batch writes a status record to `canopysense.patcher_run_log`. Query it to see the result of the last run:

```sql
SELECT afdeling_id, status, rows_inserted, api_version, triggered_at
FROM canopysense.patcher_run_log
WHERE trigger_mode = 'scheduled'
ORDER BY triggered_at DESC
LIMIT 10;
```

**Run log status meanings:**

| Status            | What It Means                                                                                           |
| ----------------- | ------------------------------------------------------------------------------------------------------- |
| `FULL_SUCCESS`    | All blocks in this afdeling processed successfully                                                      |
| `PARTIAL_SUCCESS` | Some blocks succeeded; others failed (e.g. cloud cover too high on specific blocks) — will be retried   |
| `FULL_FAILURE`    | The entire afdeling batch failed (network error, timeout, etc.) — will be retried on next scheduled run |
| `SKIPPED`         | Batch was skipped — either empty block list or already succeeded recently                               |
| `IN_PROGRESS`     | Batch is currently running (should disappear within minutes)                                            |

---

### B.3 Expected Runtime and Data Freshness

| Metric                        | Expected Value                                                    |
| ----------------------------- | ----------------------------------------------------------------- |
| Typical runtime               | 3–8 minutes per afdeling batch                                    |
| Total scheduled run time      | Batches × 3–8 min each (runs sequentially)                        |
| Cold start delay (first call) | +5–10 seconds per batch                                           |
| Data freshness                | Satellite scenes from the last 7 days                             |
| Rows per run                  | Varies by number of blocks (typically 50–200 rows total)          |
| Re-running on same data       | Safe — duplicate rows are automatically skipped                   |
| Failed batch retry            | Automatic — happens on the next scheduled run, no action required |

---

### B.4 How to Set Up Scheduled Runs

To run Patcher-Local automatically every week, add it to your server's cron scheduler:

```bash
crontab -e
```

Add this line to run every Monday at 06:00:

```
0 6 * * 1 cd /path/to/patcher_local && python3 patcher_local.py >> /var/log/patcher.log 2>&1
```

To view the scheduled log:

```bash
tail -50 /var/log/patcher.log
```

---

### B.5 Where to Find Logs

| Log Location           | What It Contains                                           |
| ---------------------- | ---------------------------------------------------------- |
| Terminal output        | Patcher-Local execution (current run only)                 |
| `/var/log/patcher.log` | All past scheduled runs (if cron is set up per B.4)        |
| Google Cloud Logging   | Server-side audit trail — all calls including auth results |

**To view Cloud Logging (requires Google Cloud Console access):**

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Select project **canopysense**
3. Navigate to **Logging → Log Explorer**
4. Use this filter:
   
   ```
   resource.type="cloud_run_revision"
   resource.labels.service_name="patcher-cloud"
   jsonPayload.audit=true
   ```
5. Look for entries with your `CONTRACTOR_ID` in the results

---

## Section C: Troubleshooting

### C.1 "Cloud Function returns 403 Forbidden"

**What it means:** Your API key was rejected. Either the key is wrong, or it has been revoked.

**Checklist:**

- [ ] Open `.env` and check `PATCHER_API_KEY` — no extra spaces, no quotes around the value
- [ ] Check that `CONTRACTOR_ID` matches exactly what your administrator assigned
- [ ] Ask your administrator if your API key has been revoked (Section E)
- [ ] If your key was recently issued, confirm you copied it completely (keys are long strings)

**Worked Example — What the error looks like:**

```
08:30:01 [INFO] — Calling Cloud Function: https://...
08:30:02 [ERROR] — Cloud Function HTTP error: 403 — {"error": "403 Forbidden: Invalid API Key (contact administrator)"}
```

→ Action: Contact your administrator with your `CONTRACTOR_ID`.

---

### C.2 "Patcher-Local timeout" or "FULL_FAILURE" on a Batch

**What it means:** A batch failed to process. The Cloud Function took too long, the network dropped, or the Cloud Function returned an error.

**What happens automatically:** The failed batch is recorded in `patcher_run_log` with status `FULL_FAILURE`. On the next scheduled run, only the failed batch is retried — successful batches are not re-run.

**Checklist:**

- [ ] Check your internet connection: `ping 8.8.8.8`
- [ ] Try increasing the timeout in `.env`: `FUNCTION_TIMEOUT_SECONDS=300`
- [ ] Check `patcher_run_log` to confirm which afdeling failed and what the error was:
  
  ```sql
  SELECT afdeling_id, status, error_detail, triggered_at
  FROM canopysense.patcher_run_log
  WHERE status = 'FULL_FAILURE'
  ORDER BY triggered_at DESC LIMIT 5;
  ```
- [ ] If it keeps failing, check Cloud Logging for server-side errors (Section B.5)

**Worked Example (v0.9 retry backoff output):**

```
08:30:01 [WARN]  Attempt 1 failed (timeout). Retrying in 30s...
08:30:31 [WARN]  Attempt 2 failed (timeout). Retrying in 60s...
08:31:31 [WARN]  Attempt 3 failed (timeout). Retrying in 120s...
08:33:31 [ERROR] Batch 2/3 — FULL_FAILURE after 3 attempts. Recorded for next run.
```

→ The run continues with the next batch. Batch 2 will be retried automatically on the next scheduled run.

---

### C.3 "PostGIS ingestion failed"

**What it means:** The satellite data was received from the cloud, but writing to your local database failed.

**Checklist:**

- [ ] Verify PostgreSQL is running: `pg_isready -h localhost -p 5432`
- [ ] Check your database credentials in `.env` (`PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`)
- [ ] Verify the `satellite_data` table exists: `psql -U your_user -d canopysense -c "\dt canopysense.satellite_data"`
- [ ] Check disk space: `df -h`

**Worked Example:**

```
[ERROR] — 500 Internal Server Error: PostGIS ingestion failed (reason in logs) — 08P01
```

→ Action: Check database connectivity. The `08P01` is a PostgreSQL error code — look it up or contact your DBA.

---

### C.4 How to Check Cloud Logging for Server-Side Errors

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Select project **canopysense**
3. Go to **Logging → Log Explorer**
4. Use this filter:
   
   ```
   resource.type="cloud_run_revision"
   resource.labels.service_name="patcher-cloud"
   jsonPayload.audit=true
   ```
5. Look for entries with `"status": "ENGINE_ERROR"` or `"status": "TIMEOUT"`

**What a successful audit log entry looks like:**

```json
{
  "audit": true,
  "timestamp": "2026-04-20T08:30:05Z",
  "contractor_id": "CONTRACTOR_ACME",
  "status": "SUCCESS",
  "detail": "rows=84"
}
```

---

### C.5 How to Manually Verify Core Engine Output

If you want to confirm what data was processed before it reached your database:

```sql
-- Check the most recent acquisition date in your database
SELECT MAX(acquisition_date) AS latest_data FROM canopysense.satellite_data;

-- Check data for a specific date
SELECT block_id, sensor, ndvi, evi, cloud_cover
FROM canopysense.satellite_data
WHERE acquisition_date = '2026-04-18'
ORDER BY block_id;
```

If `MAX(acquisition_date)` is more than 14 days ago, the extraction may not be running. Check the Cloud Logging for recent `AUTH_OK` entries.

---

## Section D: Security Best Practices

> **These rules protect your organization's data and access. Violations can result in unauthorized access to your satellite data pipeline.**

### D.1 Rules You Must Follow

| Rule                                           | Why It Matters                                                                         |
| ---------------------------------------------- | -------------------------------------------------------------------------------------- |
| **Never commit `.env` to git**                 | Exposes your API key to anyone with repo access                                        |
| **Never share your API key**                   | Each key is unique to your organization — sharing it lets others use your access quota |
| **Never hardcode the API key in scripts**      | If the script is shared, your key is exposed                                           |
| **Rotate your API key quarterly**              | Limits damage if a key is ever accidentally leaked                                     |
| **Monitor Cloud Logging for unexpected calls** | Detects if someone is using your key without authorization                             |

### D.2 How to Rotate Your API Key

Rotating means getting a new key issued to replace your current one:

1. Contact your administrator and request a new API key for your `CONTRACTOR_ID`
2. Administrator will issue a new key and mark your old key as REVOKED
3. Update `PATCHER_API_KEY` in your `.env` file with the new value
4. Test with `python patcher_local.py` to confirm the new key works
5. Securely delete any notes or emails containing the old key

> **Tip:** Set a calendar reminder every 3 months to rotate your key.

### D.3 What to Do If You Suspect Your Key Was Leaked

1. Contact your administrator **immediately** with your `CONTRACTOR_ID`
2. Administrator will revoke your old key (takes <30 seconds)
3. Any unauthorized calls will immediately start receiving `403 Forbidden`
4. Administrator will issue you a new key
5. Update `.env` with the new key and test

---

## Section E: Access Control & Revocation

### E.1 How API Key Revocation Works

When your administrator revokes your API key:

- The key status is changed to `REVOKED` in Google Cloud Secret Manager
- This takes effect on the **very next call** — no restart or redeployment needed
- All subsequent calls from your server return `403 Forbidden: API Key revoked`

**Worked Example — What you see after revocation:**

```
08:30:01 [INFO] — Calling Cloud Function: https://...
08:30:02 [ERROR] — Cloud Function HTTP error: 403 — 
  {"error": "403 Forbidden: API Key revoked (issued 2026-04-20, revoked 2026-04-25)"}
```

### E.2 How to Request a New API Key

If your key is lost, expired, or revoked:

1. Email your administrator with subject: `CanopySense: New API Key Request`
2. Include your `CONTRACTOR_ID` in the email
3. Administrator will generate a new key and send it to you via a secure channel (not plain email)
4. Update your `.env` file with the new value
5. Test: `python patcher_local.py`

### E.3 What Happens to Your Data When a Key Is Revoked

- **Your existing database data is unaffected.** Revocation only blocks future extraction runs.
- **Scheduled runs will fail** (they will log `403 Forbidden` errors) until a new key is configured.
- **No historical data is deleted.** Your `satellite_data` table remains intact.

### E.4 Emergency Steps If You Suspect a Security Breach

1. **Immediately** contact your administrator by phone (not just email)
2. Request emergency revocation of your API key
3. Document the incident: when you noticed it, what looked wrong
4. After revocation is confirmed, change your local PostGIS password as a precaution
5. Review Cloud Logging (Section B.5) for unauthorized calls using your `CONTRACTOR_ID`

---

## Section F: Disaster Recovery

### F.1 What to Do If the Cloud Function Is Down

**Signs the Cloud Function is down:**

- `ConnectionError` or `HTTPError 500` in your logs
- Cloud Logging shows no entries for the past hour

**Steps:**

1. Wait 10 minutes and retry (Cloud Functions auto-recover from temporary outages)
2. Check Google Cloud Status: [status.cloud.google.com](https://status.cloud.google.com)
3. If the outage persists >1 hour, contact your administrator

**Temporary workaround:** Your existing `satellite_data` records remain available for analysis. No data is lost during a Cloud Function outage — only new extraction runs are blocked.

---

### F.2 Retry Escalation Timeline

| Time Since First Failure                       | Action                                                                          |
| ---------------------------------------------- | ------------------------------------------------------------------------------- |
| 0–3.5 minutes                                  | Patcher-Local automatically retries with backoff (30s → 60s → 120s)             |
| After 3 attempts fail                          | Batch marked `FULL_FAILURE` in `patcher_run_log`; run continues with next batch |
| Next scheduled run                             | Failed batch retried automatically — no action required                         |
| If same batch fails 3+ scheduled runs in a row | Check Cloud Logging for server-side errors; escalate to administrator           |

**To force an immediate retry of all failed batches without waiting for the next scheduled run:**

```bash
python3 patcher_local.py
```

The script will detect the `FULL_FAILURE` entries in `patcher_run_log` and retry them first.

---

### F.3 Where to Find Backup Logs

| Type                   | Location                                        |
| ---------------------- | ----------------------------------------------- |
| Local run logs         | `/var/log/patcher.log` (if cron is set up)      |
| Cloud-side audit trail | Google Cloud Logging → `patcher_cloud` function |
| Previous run results   | Your local `canopysense.satellite_data` table   |

To export the last 30 days of your satellite data as a backup:

```sql
COPY (
  SELECT * FROM canopysense.satellite_data
  WHERE acquisition_date >= CURRENT_DATE - INTERVAL '30 days'
) TO '/tmp/satellite_data_backup.csv' WITH CSV HEADER;
```

---

### F.4 How to Manually Verify Your System Is Healthy

Run this end-to-end health check:

**1. Check Python and dependencies:**

```bash
python --version
python -c "import requests, dotenv, psycopg2; print('Dependencies OK')"
```

Expected: `Dependencies OK`

**2. Check PostGIS connection:**

```bash
python -c "
import os; from dotenv import load_dotenv; load_dotenv()
import psycopg2
conn = psycopg2.connect(
  host=os.environ['PGHOST'], dbname=os.environ['PGDATABASE'],
  user=os.environ['PGUSER'], password=os.environ['PGPASSWORD']
)
print('PostGIS OK — version:', conn.server_version); conn.close()
"
```

Expected: `PostGIS OK — version: 140001` (or similar version number)

**3. Check Cloud Function reachability:**

```bash
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" \
  -X POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud \
  -H "Content-Type: application/json"
```

Expected: `HTTP Status: 401` (no key provided — this confirms the URL is working)

**4. Run Patcher-Local:**

```bash
python patcher_local.py
```

Expected: Final log line shows `Patcher-Local complete.`

---

## Appendix: Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│           CANOPYSENSE PATCHER-LOCAL QUICK REF v0.10      │
├─────────────────────────────────────────────────────────┤
│ Scheduled run (all blocks):                             │
│   python3 patcher_local.py                              │
│                                                         │
│ Upload trigger (one block):                             │
│   python3 patcher_local.py --block-id 42               │
│                                                         │
│ Check DB data:   SELECT COUNT(*) FROM                   │
│                  canopysense.satellite_data;             │
│ Check run log:   SELECT afdeling_id,status,triggered_at │
│                  FROM canopysense.patcher_run_log        │
│                  ORDER BY triggered_at DESC LIMIT 10;   │
│ Check logs:      tail -50 /var/log/patcher.log          │
│                                                         │
│ Error 401 → Missing API key in .env                     │
│ Error 403 → Wrong or revoked API key (stops entire run) │
│ FULL_FAILURE → Retried automatically next scheduled run │
│ PARTIAL_SUCCESS → Missing blocks retried next run       │
│                                                         │
│ Emergency contact: your administrator                   │
│ Key revocation: takes effect in <30 seconds             │
└─────────────────────────────────────────────────────────┘
```

---

*CanopySense Patcher-Local GUIDANCE.md — v0.10 — 2026-04-25*
