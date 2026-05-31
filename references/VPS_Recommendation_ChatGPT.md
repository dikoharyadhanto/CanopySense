# VPS Recommendation — CanopySense Development & Deployment Strategy

## 1. Context

CanopySense is still in the **development phase**. The immediate objective is not to choose the final production server, but to create a reliable environment where the application can be built, deployed, tested, and observed under realistic conditions.

The original server recommendation document correctly identifies that CanopySense will eventually require a **medium-class server** because the system depends heavily on PostgreSQL, PostGIS, spatial indexing, time-series queries, FastAPI, React, and data ingestion from Google Earth Engine / GCP workflows.

However, because the project is not yet in production, the server decision should be staged rather than treated as a single irreversible commitment.

---

## 2. Core Decision

**Use Google Cloud first for development/staging, but do not treat it as the final production commitment.**

Google Cloud should be used as a temporary proving ground because:

1. CanopySense already has architectural affinity with Google Earth Engine and GCP workflows.
2. The project is still in development, so migration risk is low.
3. There are no production users, no hard SLA, and no critical uptime obligation yet.
4. GCP allows early testing of deployment, networking, environment variables, logging, CORS, SSL, database connectivity, and ingestion flows.
5. It prevents premature commitment to IDCloudHost or Biznet before the actual application behavior is measured.

The recommended framing is:

> **GCP = development/staging proving ground.**  
> **IDCloudHost/Biznet = production candidates after the system is technically proven.**

---

## 3. Important Clarification About Cost

Current billing activity in Google Cloud is very small, but it exists even before full deployment. This means the project is already generating residual cloud cost from early GCP usage such as Cloud Build, Cloud Run Functions, Cloud Storage, logging, or related services.

This is not a financial problem by itself. The amount is insignificant. The real concern is **cost visibility**.

Before deploying the full CanopySense development stack, the source of existing costs should be understood.

The key question is:

> **Where exactly does the current GCP cost come from?**

If the source is known and controlled, deployment can continue. If the source is unclear, billing should be audited first so future development costs can be attributed correctly.

---

## 4. Required Pre-Deployment Billing Hygiene

Before creating a development VM or deploying the application stack, perform the following checks:

1. Open **Billing → Cost table** and identify the exact SKU causing the current cost.
2. Check **Cloud Build → History** for unnecessary or repeated builds.
3. Check **Cloud Run / Cloud Run Functions** for active or leftover functions.
4. Check **Cloud Storage** for unused buckets, artifacts, or temporary files.
5. Check **Artifact Registry / Container Registry** for unused images.
6. Check **Logging** for excessive log ingestion or retained logs.
7. Check **Compute Engine** for any VM, persistent disk, snapshot, or static IP that may have been created unintentionally.
8. Create a **budget alert** before deploying the application.

Recommended initial budget alert:

| Item                 | Recommendation      |
| -------------------- | -------------------:|
| Monthly budget alert | Rp100.000           |
| Alert thresholds     | 50%, 80%, 100%      |
| Scope                | CanopySense project |

This budget is not because Rp100.000 is a major cost, but because it creates operational discipline early.

---

## 5. Recommended Development Architecture on GCP

For the development phase, the architecture should stay portable and simple.

Recommended setup:

| Component          | Development Recommendation                 |
| ------------------ | ------------------------------------------ |
| Compute            | 1 Compute Engine VM                        |
| Backend            | FastAPI running on VM                      |
| Frontend           | React build served by Nginx                |
| Database           | PostgreSQL + PostGIS installed on VM       |
| Reverse proxy      | Nginx                                      |
| SSL                | Certbot / Let's Encrypt                    |
| Config             | `.env` files                               |
| Process management | Docker Compose or systemd                  |
| Backup             | `pg_dump` / `pg_restore`                   |
| Logging            | Basic VM logs + optional GCP Cloud Logging |

Recommended VM profile for development/staging:

| Option        | Use Case                                           |
| ------------- | -------------------------------------------------- |
| e2-standard-2 | Lower-cost development baseline, 2 vCPU / 8 GB RAM |
| e2-standard-4 | More realistic staging test, 4 vCPU / 16 GB RAM    |

For early development, **e2-standard-2** is acceptable if the workload is still small. For closer production simulation, **e2-standard-4** is better.

---

## 6. What to Avoid During Development

To preserve migration flexibility, avoid premature dependence on heavily managed GCP-specific services.

Avoid for now:

| Service / Pattern                      | Reason                                                                            |
| -------------------------------------- | --------------------------------------------------------------------------------- |
| Cloud SQL                              | Convenient, but introduces managed-service dependency and potentially higher cost |
| Full Cloud Run deployment              | Good later, but adds GCP-specific deployment behavior                             |
| App Engine                             | Too platform-specific for current needs                                           |
| Kubernetes / GKE                       | Overkill for development                                                          |
| Complex Cloud Build pipelines          | Can create unnecessary cost and complexity                                        |
| Secret Manager as mandatory dependency | Useful later, but `.env` is enough for development                                |
| Large Cloud Storage datasets           | Avoid uploading heavy raster/GeoTIFF data before necessary                        |

The development stack should remain movable with minimal friction.

A good portability target is:

```bash
docker compose up -d
```

or, if not using Docker Compose:

```bash
systemctl start postgresql
systemctl start api
systemctl start nginx
```

If the application can run this way, migration to IDCloudHost or Biznet later is straightforward.

---

## 7. Migration Risk Assessment

Migration is not a major risk at this stage because:

1. The system is not yet production-facing.
2. There are no external users depending on uptime.
3. The database is still small enough to dump and restore.
4. Schema changes are still expected.
5. Downtime is acceptable during development.
6. DNS and environment variables can still be changed without user impact.

A future migration from GCP to IDCloudHost or Biznet would follow this basic process:

1. Stop writes to the development database.
2. Run `pg_dump` from the GCP VM.
3. Provision the new VPS.
4. Install PostgreSQL, PostGIS, Nginx, and the application runtime.
5. Restore with `pg_restore` or `psql`.
6. Copy `.env` configuration.
7. Deploy backend and frontend.
8. Update DNS.
9. Validate login, map rendering, API responses, and ingestion.

This is work, but not a strategic blocker during development.

---

## 8. When to Move Away From GCP

GCP should be evaluated after 7–14 days of real development/staging usage.

Decision table:

| Observed Condition                                         | Recommended Action                               |
| ---------------------------------------------------------- | ------------------------------------------------ |
| Cost remains low and system is still changing rapidly      | Stay on GCP development/staging                  |
| Deployment is stable but GCP cost looks high               | Prepare migration to IDCloudHost or Biznet       |
| Demo deadline is near and GCP is stable                    | Keep GCP temporarily for demo                    |
| Production Fase 1 is ready and cost predictability matters | Move to IDCloudHost NVME 5                       |
| Budget is extremely tight                                  | Consider Biznet Gio NEO Lite MM 8.4              |
| PostGIS/query performance becomes critical                 | Prefer IDCloudHost NVME 5 or equivalent NVMe VPS |

---

## 9. Production Candidate Decision

For production Fase 1, the original recommendation remains valid:

### Preferred production candidate

**IDCloudHost NVME 5**

Indicative profile:

- 4 vCPU
- 8 GB RAM
- 140 GB NVMe
- Better fit for PostgreSQL/PostGIS and spatial workloads
- More appropriate for stable production deployment

### Low-cost alternative

**Biznet Gio NEO Lite MM 8.4**

Indicative profile:

- 4 vCPU
- 8 GB RAM
- Significantly cheaper
- Acceptable for development or cost-constrained staging
- Needs caution around network behavior and international transfer assumptions

### Not recommended

Small VPS instances with only 1–2 GB RAM should be avoided for CanopySense because PostgreSQL + PostGIS can easily exceed that memory profile, especially once spatial indexing and time-series data are involved.

Large/bare metal servers are also not justified for Fase 1 because CanopySense is not yet running heavy AI/ML training, STL decomposition, or large-scale multi-tenant analytics.

---

## 10. Final Recommendation

The recommended path is:

1. **Audit current GCP billing first.**
2. **Clean up unused resources.**
3. **Create a Rp100.000 monthly budget alert.**
4. **Deploy CanopySense to GCP as a development/staging environment.**
5. **Keep the architecture portable: VM, PostgreSQL/PostGIS, FastAPI, React, Nginx, `.env`, Docker Compose or systemd.**
6. **Measure actual cost and performance for 7–14 days.**
7. **Only then decide whether to stay temporarily on GCP or migrate production to IDCloudHost/Biznet.**

Final position:

> **Use GCP now, but do not marry GCP yet.**  
> **Let GCP prove the system. Let IDCloudHost/Biznet compete later for production economics.**

---

## 11. Director-Level Summary

The immediate decision is not “which production VPS should be purchased?”

The immediate decision is:

> **Where should CanopySense first meet real deployment conditions without creating premature vendor lock-in or uncontrolled cost?**

Answer:

> **Google Cloud, temporarily, as a controlled development/staging environment.**

The cost concern is valid, but currently not material. The bigger risk is unclear cost attribution. Therefore, billing hygiene and budget alerts must come before full deployment.

Once CanopySense proves its end-to-end pipeline, the production server decision becomes easier and evidence-based.
