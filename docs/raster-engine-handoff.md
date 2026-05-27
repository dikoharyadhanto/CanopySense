# CanopySense Raster Engine — v1.7 Explore Map UI Handoff

> Contract document for Plan v1.7 frontend integration.
> Produced by DEV-EXEC v1.6. Backend-authoritative — do not infer behavior from this doc alone; always verify against live API.

---

## 1. Overview

The raster engine provides on-demand satellite imagery tiles for the Explore Map page. It returns a metadata contract describing the tile URL, vegetation index, sensor, date window, and subscription tier. The UI must never cache tile URLs beyond the session — they expire in ~48 hours.

---

## 2. Endpoint

```
GET /api/raster/metadata
Authorization: Bearer <JWT>
```

### Query Parameters

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `index` | string | No (default: `ndvi`) | Vegetation index. Supported: `ndvi`, `evi`, `savi`, `gndvi`, `ndre` |
| `date_start` | ISO date | No | Timelapse window start. **Premium only** — ignored for basic. |
| `date_end` | ISO date | No | Timelapse window end. **Premium only** — ignored for basic. |

### Response (HTTP 200)

```json
{
  "schema_version": "1.0",
  "serving_mode": "gee_mapid",
  "subscription_tier": "basic",
  "index": "ndvi",
  "sensor": "S2",
  "date_acquired": "2026-05-21",
  "date_window_start": "2026-05-14",
  "date_window_end": "2026-05-21",
  "valid_pixel_ratio": 0.847,
  "low_quality": false,
  "bounds": {
    "west": 104.12,
    "south": -3.22,
    "east": 104.51,
    "north": -2.98
  },
  "resolution_m": 10,
  "palette": ["red", "yellow", "green"],
  "viz_min": -0.2,
  "viz_max": 0.9,
  "tile_url_format": "https://earthengine.googleapis.com/v1/...",
  "tile_url_expires_note": "~48 hours from generation (GEE getMapId limitation). v1.7 UI must call this endpoint on each page load to get a fresh URL.",
  "cloud_nodata_note": "Cloudy and shadowed pixels are masked. Unmasked pixels represent clear-sky surface reflectance. Masked pixels render as transparent.",
  "generated_at_utc": "2026-05-27T10:00:00+00:00"
}
```

---

## 3. Subscription Tier Behavior

Subscription tier is determined by the backend from `company_subscriptions` on every request. **The UI must not make routing decisions based on JWT claims.**

| Tier | Serving Mode | Date Params | Behavior |
| :--- | :--- | :--- | :--- |
| `basic` | `gee_mapid` | Ignored | Always returns latest 7-day window. No timestamp slider. |
| `premium` | `maps_platform` | Used if provided | Accepts `date_start`/`date_end` within `timelapse_period_months`. Slider enabled. |

### UI Rules

- If `subscription_tier == "basic"`: hide timestamp slider; show "Latest data" label.
- If `subscription_tier == "premium"`: show timestamp slider limited to the allowed lookback period (query `/auth/me` for `subscription_tier`, but always validate on backend).
- If `date_start` outside allowed window: backend returns `403 Forbidden` with a clear message — display it to the user, do not silently ignore.

---

## 4. Tile URL Usage (Leaflet / Maps SDK)

The `tile_url_format` field is a Leaflet-compatible XYZ tile URL template:

```javascript
L.tileLayer(metadata.tile_url_format, {
  maxZoom: 18,
  opacity: 0.85,
  attribution: "Google Earth Engine"
}).addTo(map);
```

**Critical constraint**: tile URLs expire in ~48 hours. The UI must:
1. Call `GET /api/raster/metadata` on every Explore Map page load.
2. Never store tile URLs in localStorage or session storage beyond the page session.
3. If the tile URL returns 403/404 (expired), re-call the endpoint to get a fresh URL — do not show a generic network error.

---

## 5. Supported Indices

| Index | Sensor Requirement | Viz Palette | Min/Max |
| :--- | :--- | :--- | :--- |
| `ndvi` | S2, L8, L9 | red → yellow → green | -0.2 / 0.9 |
| `evi` | S2, L8, L9 | red → yellow → green | -0.2 / 0.9 |
| `savi` | S2, L8, L9 | #8B4513 → yellow → green | -0.2 / 0.9 |
| `gndvi` | S2, L8, L9 | red → yellow → darkgreen | -0.2 / 0.9 |
| `ndre` | **S2 only** | purple → white → green | -0.2 / 0.9 |

If the scene is Landsat and the user requests `ndre`, the endpoint returns `503 Service Unavailable` with an explanatory message. The UI must handle this gracefully — suggest an alternative index or inform the user.

---

## 6. Error States

| HTTP Status | Condition | UI Recommended Action |
| :--- | :--- | :--- |
| `401 Unauthorized` | No/invalid JWT | Redirect to login |
| `402 Payment Required` | No active subscription or expired | Show subscription error, contact info |
| `403 Forbidden` | Date outside timelapse window | Show "Date out of range" message with allowed range |
| `404 Not Found` | No estate blocks for company | Show "No estate data configured" message |
| `422 Unprocessable Entity` | Invalid index name | Developer error — fix query param |
| `503 Service Unavailable` | No valid scene (cloud, etc.) or NDRE on Landsat | Show "No imagery available for this date" message; suggest 7-day retry |

---

## 7. Metadata Fields Glossary

| Field | Type | Notes |
| :--- | :--- | :--- |
| `schema_version` | string | `"1.0"` — bump if schema changes |
| `serving_mode` | string | `"gee_mapid"` or `"maps_platform"` |
| `subscription_tier` | string | `"basic"` or `"premium"` — display context only |
| `index` | string | Vegetation index that was computed |
| `sensor` | string | `"S2"` (10m), `"L8"` or `"L9"` (30m) |
| `date_acquired` | ISO date | Best scene date within the window |
| `date_window_start` | ISO date | Search window start |
| `date_window_end` | ISO date | Search window end |
| `valid_pixel_ratio` | float 0–1 | Fraction of clear (unmasked) pixels |
| `low_quality` | boolean | `true` if Landsat scene with ratio 0.2–0.6 |
| `bounds` | object | WGS84 bounding box — use to fit map view |
| `resolution_m` | int | Native pixel size in meters |
| `palette` | string[] | Color stops for legend rendering |
| `viz_min` / `viz_max` | float | Index range mapped to palette ends |
| `tile_url_format` | string | Leaflet XYZ template — **expires ~48h** |
| `tile_url_expires_note` | string | Human-readable expiry notice |
| `cloud_nodata_note` | string | Transparency/masking explanation for legend |
| `generated_at_utc` | ISO 8601 | Generation timestamp — use for display |

---

## 8. Pixel vs Block Semantics

The raster pixels and the block-level NDVI values in `canopysense.satellite_data` are **not directly comparable**:

- Raster pixels: full spatial resolution (10m S2 or 30m Landsat) per pixel
- Block DB values: mean index over all valid pixels within each block polygon

The UI should not display pixel values as if they equal the block summary statistics. Use raster for visual exploration; use `GET /api/blocks/{id}/indices` for block-level numeric data. Both use consistent formulas (see `src/core_engine/index_calculator.py`) but aggregate at different spatial scales.

---

## 9. Authentication and Subscription

- Authentication: JWT Bearer token from `POST /auth/login`
- Subscription context: `GET /auth/me` returns `subscription_tier` for UI display (e.g., show/hide slider)
- Subscription authority: **backend only** — backend re-reads `company_subscriptions` on every raster request; the UI must not grant premium access based on JWT content alone
- If a user is not associated with a company (`company_id` is null), raster endpoint returns `403 Forbidden`

---

## 9b. Raster Cache Behavior (v1.6)

The backend maintains a **company-scoped Redis cache** for raster metadata to prevent duplicate provider calls.

### How it works

- Cache key: `raster:v1:{company_id}:{index}:{date_start}:{date_end}:{serving_mode}`
- Cache scope: per company — all users in the same company share one cached entry for an identical raster request
- Cache TTL: configured by operator via `RASTER_CACHE_TTL_SECONDS` (default 43200 = 12h); referenced from GEE getMapId() empirical ~48h window
- Cache stores: metadata JSON only — no tile image content is cached

### Behavior the UI must understand

- Two users in the same company requesting the same index/date will receive the **same tile URL** from cache — this is correct and expected
- The `generated_at_utc` field in the response reflects when the metadata was originally generated (may be up to `RASTER_CACHE_TTL_SECONDS` ago)
- UI should still call the endpoint on each page load — caching is transparent; the endpoint always returns valid metadata
- If the cached tile URL becomes invalid (expired before cache TTL), re-calling the endpoint will still return the stale cached URL until cache expiry — see Known Limitations below

---

## 10. Known Limitations (v1.6)

| Limitation | Impact | Expected Resolution |
| :--- | :--- | :--- |
| Tile URL expires ~48h | Stored URLs become invalid; must re-fetch | v1.7 must call endpoint on page load |
| GEE credentials required at runtime | Endpoint returns 500 if backend is not configured with GEE service account | Configure `EE_SERVICE_ACCOUNT_KEY` in backend `.env` |
| NDRE not available for Landsat | 503 returned if Landsat selected and ndre requested | Show alternative index suggestion in UI |
| Geografi UI (company 2) has no estate blocks in DB | 404 returned for company 2 raster requests until estate data is seeded | Seed estate+block data for company 2 before v1.7 integration test |
| `maps_platform` mode uses same `getMapId()` mechanism in v1.6 | Tile URL still has ~48h expiry even for premium; true Maps Platform HTTP serving is v1.7 | v1.7 can implement true Maps Platform tile proxying if needed |
| Cache TTL (12h default) may hold a tile URL that expired before cache eviction | If GEE URL expires before cache TTL, cached response returns stale tile URL | v1.7 can add `If-None-Match`/ETag support or frontend-side URL validation |
