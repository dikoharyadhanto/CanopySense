# CanopySense — API Reference (Phase 1)

**Base URL (dev):** `http://localhost:8000`  
**Framework:** FastAPI (Python 3.11+)  
**Auth:** JWT Bearer token (HS256)  

All protected endpoints require the header:
```
Authorization: Bearer <access_token>
```

---

## Health

### `GET /health`

Liveness probe. No auth required.

**Response 200**
```json
{ "status": "ok" }
```

---

## Auth — `/auth`

### `POST /auth/login`

Authenticate and receive a JWT access token.

**Request** — `application/x-www-form-urlencoded`

| Field | Type | Required |
| :--- | :--- | :--- |
| `username` | string | Yes |
| `password` | string | Yes |

**Response 200**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 604800
}
```

`expires_in` is in seconds (default: 604800 = 7 days, configured via `ACCESS_TOKEN_EXPIRE_MINUTES`).

**Response 401** — invalid credentials
```json
{ "detail": "Incorrect username or password" }
```

**JWT Claims**

| Claim | Description |
| :--- | :--- |
| `sub` | Username |
| `user_id` | User integer ID |
| `company_id` | User's primary company ID |
| `role` | Role from `user_company_roles` (e.g., `manager`) |
| `exp` | Expiry timestamp |

**Seed credential (Phase 1 only)**
- Username: `manager` / Password: `password`

---

### `GET /auth/me`

Return the authenticated user's context. Requires a valid Bearer token.

**Response 200**
```json
{
  "username": "manager",
  "role": "Manager",
  "company_id": 1
}
```

**Notes**
- This endpoint is the authoritative server-side source for user context.
- The frontend decodes the same fields from the JWT for display-only purposes (sidebar username/role).
  Authorization is always enforced by this and other protected endpoints, not by the frontend JWT decode.

**Response 401** — missing or invalid token

---

## Blocks — `/api`

All `/api` endpoints require a valid Bearer token. Responses are filtered to the authenticated user's `company_id`.

---

### `GET /api/blocks`

Return all blocks with their latest satellite indices.

**Query Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `estate_id` | integer (optional) | Filter by estate |
| `afdeling_id` | integer (optional) | Filter by afdeling |

**Response 200** — array of block objects

```json
[
  {
    "block_id": 1,
    "code": "A-01",
    "name": "Block A-01",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[107.0, -0.5], ...]]
    },
    "afdeling_name": "Afdeling A",
    "estate_name": "Estate Alpha",
    "latest_ndvi": 0.6423,
    "latest_evi": 0.4211,
    "latest_ndre": 0.3812,
    "latest_savi": 0.5001,
    "latest_gndvi": 0.5782,
    "acquisition_date": "2024-03-15",
    "cloud_cover": 5.2
  }
]
```

**Notes**
- `geometry` is a GeoJSON Polygon object (parsed from PostGIS `ST_AsGeoJSON`)
- `latest_*` fields reflect the most recent `satellite_data` row per block (by `acquisition_date DESC`)
- All index fields are `null` if no satellite data exists for the block
- `acquisition_date` is ISO 8601 date string (`YYYY-MM-DD`)

---

### `GET /api/blocks/{block_id}/indices`

Return the full vegetation index time series for a single block.

**Path Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `block_id` | integer | Block ID |

**Query Parameters**

| Parameter | Alias | Type | Description |
| :--- | :--- | :--- | :--- |
| `from` | `from_date` | date (YYYY-MM-DD, optional) | Start of date range (inclusive) |
| `to` | `to_date` | date (YYYY-MM-DD, optional) | End of date range (inclusive) |

**Response 200** — array of index rows, ordered by `acquisition_date ASC`

```json
[
  {
    "acquisition_date": "2021-06-10",
    "sensor": "sentinel-2",
    "cloud_cover": 3.5,
    "ndvi": 0.5912,
    "evi": 0.4103,
    "ndre": 0.3201,
    "savi": 0.4887,
    "gndvi": 0.5341
  },
  {
    "acquisition_date": "2021-07-14",
    "sensor": "landsat-8",
    "cloud_cover": 12.0,
    "ndvi": 0.5644,
    "evi": 0.3981,
    "ndre": null,
    "savi": 0.4712,
    "gndvi": 0.5198
  }
]
```

**Notes**
- `ndre` is `null` for `landsat-8` rows (band not available on Landsat-8)
- `cloud_cover > 30` is the UI threshold for flagging high-cloud observations (red dashed line in time-series chart)
- Results are ordered ascending by date (oldest first)

**Response 404** — block not found or does not belong to user's company
```json
{ "detail": "Block not found" }
```

---

## Error Format

FastAPI default error envelope:

```json
{
  "detail": "<error message>"
}
```

Standard HTTP status codes:
- `401` — missing or invalid token
- `403` — forbidden
- `404` — resource not found
- `422` — validation error (malformed request)

---

## Authentication Flow (Full Sequence)

```
Client                          FastAPI
  │                               │
  │  POST /auth/login             │
  │  username=manager             │
  │  password=password            │
  │ ────────────────────────────► │
  │                               │  SELECT users JOIN user_company_roles
  │                               │  verify bcrypt hash
  │  200 {access_token, ...}      │
  │ ◄──────────────────────────── │
  │                               │
  │  GET /api/blocks              │
  │  Authorization: Bearer <jwt>  │
  │ ────────────────────────────► │
  │                               │  decode JWT → company_id
  │                               │  query blocks WHERE company_id = $1
  │  200 [...]                    │
  │ ◄──────────────────────────── │
```

---

## Planned Phase 2 Endpoints (not yet implemented)

| Endpoint | Description |
| :--- | :--- |
| `GET /api/anomalies` | List open anomalies for company |
| `GET /api/alerts` | List unread alerts for current user |
| `POST /api/field-inspections` | Submit field inspection result |
| `GET /api/estates` | List estates with boundaries |
| `GET /api/reports/export` | Export indices as CSV/XLSX |
