# CanopySense — Database Schema Documentation (v2)

**Engine:** PostgreSQL 14+ with PostGIS extension  
**SRID:** 4326 (WGS 84) throughout  
**File:** `database/schema.sql`

---

## Table Overview

| # | Table | Purpose |
| :--- | :--- | :--- |
| 1 | `companies` | Tenant root — every data row links back here |
| 2 | `themes` | UI theme configurations (colors) |
| 3 | `company_settings` | Per-company UI overrides (logo, theme, CSS) |
| 4 | `users` | Application users with local-auth support |
| 5 | `company_invitations` | Token-based invite flow |
| 6 | `user_company_roles` | Many-to-many user ↔ company with role assignment |
| 7 | `estates` | Top-level plantation unit (MultiPolygonZ) |
| 8 | `afdelings` | Sub-division of an estate (MultiPolygon) |
| 9 | `blocks` | Smallest management unit (Polygon) |
| 10 | `satellite_data` | Vegetation indices per block per date (append-only) |
| 11 | `ground_truth` | Field-measured canopy greenness (GCC) |
| 12 | `predictions` | ML-model GCC predictions per satellite record |
| 13 | `anomalies` | Detected deviations between predicted and actual GCC |
| 14 | `alerts` | User-targeted notifications for anomalies |
| 15 | `field_inspections` | On-site verification of anomalies |

---

## Table Details

### 1. `companies`

Tenant root. Every row in `estates`, `blocks`, `users`, etc. carries a `company_id` FK pointing here to enforce data isolation.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | Internal integer key |
| `company_id` | UUID UNIQUE | External UUID identifier |
| `company_name` | VARCHAR(255) | Display name |
| `created_at` | TIMESTAMP | Auto-set |
| `metadata` | JSONB | Flexible key-value store |

---

### 2. `themes`

UI theming palette. Referenced by `company_settings.theme_id`.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `theme_name` | VARCHAR(100) | |
| `light_colors` | JSONB | Color tokens for light mode |
| `dark_colors` | JSONB | Color tokens for dark mode |
| `created_at` | TIMESTAMP | |

---

### 3. `company_settings`

Per-company white-label settings: logo, theme, custom CSS.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `company_id` | BIGINT → companies | |
| `app_title` | VARCHAR(255) | Default: `'CanopySense'` |
| `logo_url` | VARCHAR(500) | |
| `theme_id` | BIGINT → themes | |
| `custom_css` | TEXT | |
| `updated_at` | TIMESTAMP | |

---

### 4. `users`

Application users. `password_hash` supports local bcrypt authentication. `is_global_admin` is reserved for super-admin access across tenants.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `company_id` | BIGINT → companies | Primary tenant affiliation |
| `email` | VARCHAR(150) UNIQUE | |
| `full_name` | VARCHAR(150) | |
| `username` | VARCHAR(150) | Login credential |
| `password_hash` | VARCHAR(255) | bcrypt hash |
| `phone_number` | VARCHAR(20) | |
| `is_global_admin` | BOOLEAN | Default: FALSE |
| `is_active` | BOOLEAN | Default: TRUE |
| `created_by` | BIGINT → users | Self-referential audit FK |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

---

### 5. `company_invitations`

Token-based email invite flow. Expiry default is 7 days from creation.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `company_id` | BIGINT → companies | |
| `token` | VARCHAR(255) UNIQUE | Secure random token |
| `email` | VARCHAR(255) | Invitee email |
| `role` | VARCHAR(50) | Default: `'viewer'` |
| `created_at` | TIMESTAMP | |
| `expires_at` | TIMESTAMP | Default: NOW() + 7 days |
| `accepted_at` | TIMESTAMP | NULL until accepted |
| `accepted_by_user_id` | BIGINT → users | NULL until accepted |

---

### 6. `user_company_roles`

Resolves the many-to-many relationship between users and companies with an explicit role. A user can belong to multiple companies with different roles. The UNIQUE constraint prevents duplicate assignments.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `user_id` | BIGINT → users | |
| `company_id` | BIGINT → companies | |
| `role` | VARCHAR(50) | e.g., `manager`, `viewer` |
| `created_at` | TIMESTAMP | |
| `promoted_by` | BIGINT → users | Audit FK |

**Constraint:** `UNIQUE(user_id, company_id)`

---

### 7. `estates`

Top-level plantation boundary. Geometry is `MultiPolygonZ` (3D with elevation) in SRID 4326. Three computed columns are stored automatically.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `company_id` | BIGINT → companies | |
| `name` | VARCHAR(100) | |
| `code` | VARCHAR(20) UNIQUE | Short identifier |
| `geometry` | GEOMETRY(MultiPolygonZ,4326) | PostGIS geometry |
| `envelope` | GEOMETRY (computed) | Bounding box — `ST_Envelope(geometry)` |
| `area_ha` | NUMERIC(10,2) (computed) | Area in hectares via `ST_Area(::geography)` |
| `is_valid` | BOOLEAN (computed) | `ST_IsValid(geometry)` |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

**Indexes:** GIST on `geometry`, GIST on `envelope`, B-tree on `code`, B-tree on `company_id`  
**Constraint:** `ST_IsValid(geometry) AND ST_SRID(geometry)=4326`

---

### 8. `afdelings`

Sub-division of an estate. Geometry is `MultiPolygon` (2D) in SRID 4326.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `estate_id` | BIGINT → estates | Parent estate |
| `company_id` | BIGINT → companies | Denormalized for fast tenant filter |
| `name` | VARCHAR(100) | |
| `code` | VARCHAR(20) | |
| `geometry` | GEOMETRY(MultiPolygon,4326) | |

**Indexes:** GIST on `geometry`, B-tree on `estate_id`  
**Constraint:** `GeometryType(geometry) = 'MULTIPOLYGON'`

---

### 9. `blocks`

Smallest management unit — individual planting block. Geometry is a simple `Polygon` in SRID 4326. This is the primary foreign key for all satellite and field data.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `afdeling_id` | BIGINT → afdelings | Parent afdeling |
| `company_id` | BIGINT → companies | Denormalized for fast tenant filter |
| `name` | VARCHAR(100) | |
| `code` | VARCHAR(20) UNIQUE | e.g., `A-01` |
| `geometry` | GEOMETRY(Polygon,4326) | |
| `plant_year` | INTEGER | Year of planting |
| `clone_type` | VARCHAR(50) | Oil palm clone variety |
| `area_ha` | NUMERIC(10,2) (computed) | `ST_Area(::geography)/10000` |

**Indexes:** GIST on `geometry`, B-tree on `company_id`  
**Constraint:** `GeometryType(geometry) = 'POLYGON'`

**Seed data:** 44 blocks across 4 afdelings in 1 estate.

---

### 10. `satellite_data`

Vegetation index time-series. One row per (block, date, sensor). This table is **append-only** — a trigger rejects all UPDATE and DELETE operations to preserve audit integrity.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `block_id` | BIGINT → blocks | |
| `acquisition_date` | DATE | Scene capture date |
| `sensor` | VARCHAR(20) | Default: `'sentinel-2'`; also `'landsat-8'` |
| `cloud_cover` | NUMERIC(5,2) | 0–100%; threshold for flagging is 30% |
| `ndvi` | FLOAT | Normalized Difference Vegetation Index |
| `evi` | FLOAT | Enhanced Vegetation Index |
| `ndre` | FLOAT | Normalized Difference Red Edge (NULL for Landsat-8) |
| `savi` | FLOAT | Soil-Adjusted Vegetation Index |
| `gndvi` | FLOAT | Green NDVI |
| `features` | JSONB | Raw band values or additional features |
| `created_at` | TIMESTAMP | |

**Constraint:** `UNIQUE(block_id, acquisition_date, sensor)`  
**Index:** `(block_id, acquisition_date DESC)` for fast latest-record lookup  
**Append-only trigger:** `immutable_satellite_data` via `prevent_satellite_data_update()`

**Seed data:** ~2,324 rows spanning 2021–2024 from both sensors.

---

### 11. `ground_truth`

Field-measured canopy greenness (GCC) collected by observers. Linked to both a block and optionally a satellite record for comparison.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `block_id` | BIGINT → blocks | |
| `satellite_data_id` | BIGINT → satellite_data | Optional co-registration |
| `measurement_date` | DATE | |
| `gcc_percent` | NUMERIC(5,2) | Green Canopy Cover % |
| `method` | VARCHAR(50) | e.g., `drone`, `manual` |
| `observer` | VARCHAR(100) | |
| `notes` | TEXT | |
| `created_at` | TIMESTAMP | |

---

### 12. `predictions`

ML model GCC predictions keyed to a satellite record and model version.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `satellite_data_id` | BIGINT → satellite_data | |
| `prediction_date` | DATE | Date prediction was made |
| `gcc_predicted` | FLOAT | Predicted GCC value |
| `gcc_confidence` | FLOAT | Model confidence score |
| `model_version` | VARCHAR(30) | e.g., `v1.0.0` |
| `created_at` | TIMESTAMP | |

**Constraint:** `UNIQUE(satellite_data_id, model_version)`

---

### 13. `anomalies`

Deviations between model prediction and actual GCC. Lifecycle: `OPEN → VERIFIED / FALSE_POSITIVE → RESOLVED`.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `prediction_id` | BIGINT → predictions UNIQUE | One anomaly per prediction |
| `block_id` | BIGINT → blocks | Denormalized for fast lookup |
| `actual_gcc` | FLOAT | |
| `deviation` | FLOAT | |
| `status` | VARCHAR(20) | `OPEN`, `VERIFIED`, `FALSE_POSITIVE`, `RESOLVED` |
| `detected_at` | TIMESTAMP | |
| `reviewed_at` | TIMESTAMP | |
| `reviewed_by` | BIGINT → users | |
| `notes` | TEXT | |

---

### 14. `alerts`

User-targeted notifications generated from anomalies.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `anomaly_id` | BIGINT → anomalies | |
| `user_id` | BIGINT → users | Recipient |
| `alert_type` | VARCHAR(50) | |
| `priority` | VARCHAR(20) | |
| `message` | TEXT | |
| `is_read` | BOOLEAN | Default: FALSE |
| `created_at` | TIMESTAMP | |

---

### 15. `field_inspections`

On-site verification linked 1:1 to an anomaly.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BIGSERIAL PK | |
| `anomaly_id` | BIGINT → anomalies UNIQUE | 1:1 relationship |
| `inspector_id` | BIGINT → users | |
| `actual_gcc` | FLOAT | Ground-measured GCC |
| `notes` | TEXT | |
| `photos` | JSONB | Array of photo URLs/metadata |
| `inspected_at` | TIMESTAMP | |
| `created_at` | TIMESTAMP | |

---

## Entity Relationship Summary

```
companies
  ├── company_settings (1:1)
  ├── user_company_roles (1:N)
  ├── users (1:N via company_id)
  ├── estates (1:N)
  │     └── afdelings (1:N)
  │           └── blocks (1:N)
  │                 └── satellite_data (1:N, append-only)
  │                       ├── ground_truth (1:N)
  │                       └── predictions (1:N)
  │                             └── anomalies (1:1)
  │                                   ├── alerts (1:N)
  │                                   └── field_inspections (1:1)
  └── company_invitations (1:N)
```

---

## Phase 1 Scope

Phase 1 populates and uses: `companies`, `users`, `user_company_roles`, `estates`, `afdelings`, `blocks`, `satellite_data`.

Tables `ground_truth`, `predictions`, `anomalies`, `alerts`, `field_inspections`, `themes`, `company_settings`, `company_invitations` are created but **not yet populated** — they are reserved for Phase 2 (ML pipeline + alert system).
