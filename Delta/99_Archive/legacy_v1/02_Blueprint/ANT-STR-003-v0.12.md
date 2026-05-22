---
name: ANT-STR-003-v0.12
project: Canopy Sense
status: ON HOLD — Director decision 2026-04-25: parent WO on hold pending stakeholder validation of interactive map scope
version: 0.12
created_date: 2026-04-25
prerequisite: ANT-WO-003-v0.12 implementation complete, viewer_cloud deployed
linked_wo: ANT-WO-003-v0.12
---

# ANT-STR-003-v0.12 (Test Plan — GEE Viewer Decision Support Endpoint)

---

## 1. Acceptance Rules

- Viewer `acquisition_date` in response must exactly match `canopysense.satellite_data` for the queried block — not GEE's latest available imagery
- Both tile URLs (`layers.ndvi.tile_url` and `layers.problem_mask.tile_url`) must be resolvable (no GEE auth error when fetched)
- `stats.problem_coverage_pct` is a float in range [0, 100]
- All error responses include `api_version` field
- Response time for single block ≤7s (PPX Q4 benchmark)
- `patcher_cloud_function.py` remains at 254 lines; `patcher_local.py` remains at 300 lines
- `generate_preview()` in `map_previewer.py` still produces HTML output — patcher pipeline unaffected
- Custom `?threshold=` produces different `problem_coverage_pct` than default *(conditional on FLAG-B = YES)*

---

## 2. Pre-Conditions Before Execution

- [ ] `viewer_cloud` Cloud Function deployed and returning responses
- [ ] PostGIS running (`04_Test` Docker environment) with `satellite_data` containing at least block_id=18 (from ANT-STR-003-v0.10 Phase D)
- [ ] `canopysense.blocks` contains block_id=18 with valid geometry
- [ ] Block_id=2 has no rows in `satellite_data` (failed GEE quality gate — used as "no data" test case)
- [ ] Patcher Cloud Function still deployed at `patcher_cloud` URL — for Phase F integrity check
- [ ] `VIEWER_URL` known (from `gcloud functions describe viewer_cloud --region=asia-southeast2`)

---

## 3. Testing Phases

---

### Phase A: Endpoint Contract Verification

**Goal:** Confirm response structure, required fields, and auth behavior.

**Test A-1: Auth — missing key returns 401**
```bash
curl -s -X GET "<VIEWER_URL>?block_id=18" | python3 -m json.tool
```
Pass criteria:
- HTTP 401
- Response body includes `api_version`

---

**Test A-2: Valid request — full response structure**
```bash
curl -s -X GET "<VIEWER_URL>?block_id=18" \
  -H "X-API-Key: <key>" | python3 -m json.tool
```
Pass criteria:
- HTTP 200
- `status: "success"`
- `block_id: 18`
- `acquisition_date` is a valid date string
- `sensor` is non-empty
- `threshold` is a float
- `layers.ndvi.tile_url` is a non-empty string
- `layers.ndvi.palette` is a list with 3 entries
- `layers.problem_mask.tile_url` is a non-empty string
- `layers.problem_mask.threshold` matches `threshold` field
- `stats.problem_coverage_pct` is float
- `stats.mean_ndvi` is float
- `data_warning` is null or string
- `generated_at` is present

---

**Test A-3: Unknown block returns 404**
```bash
curl -s -X GET "<VIEWER_URL>?block_id=9999" \
  -H "X-API-Key: <key>" | python3 -m json.tool
```
Pass criteria:
- HTTP 404
- Error message references block not found in blocks table

---

**Test A-4: Missing block_id returns 400**
```bash
curl -s -X GET "<VIEWER_URL>" \
  -H "X-API-Key: <key>" | python3 -m json.tool
```
Pass criteria:
- HTTP 400
- Error message references missing `block_id`

---

**Test A-5: Block with no patch data returns 404**
```bash
curl -s -X GET "<VIEWER_URL>?block_id=2" \
  -H "X-API-Key: <key>" | python3 -m json.tool
```
*(Block 2 has no data — failed GEE quality gate in ANT-STR-003-v0.10)*

Pass criteria:
- HTTP 404
- Error message instructs to run patcher first (not a generic 404)

---

**Test A-6: Invalid threshold value returns 400** *(conditional on FLAG-B = YES)*
```bash
curl -s -X GET "<VIEWER_URL>?block_id=18&threshold=bad" \
  -H "X-API-Key: <key>" | python3 -m json.tool
```
Pass criteria:
- HTTP 400
- Error references invalid threshold

---

### Phase B: Data Consistency

**Goal:** Confirm viewer uses exact patched `acquisition_date` from PostGIS — not GEE's latest available imagery.

**Step B-1: Get ground truth from PostGIS**
```bash
docker compose exec postgis psql -U patcher -d canopysense_test \
  -c "SELECT block_id, acquisition_date, sensor FROM canopysense.satellite_data WHERE block_id=18"
```
Record the `acquisition_date` and `sensor` values.

**Step B-2: Call viewer and compare**
```bash
curl -s -X GET "<VIEWER_URL>?block_id=18" -H "X-API-Key: <key>" \
  | python3 -c "
import sys, json
r = json.load(sys.stdin)
print('viewer date:', r['acquisition_date'])
print('viewer sensor:', r['sensor'])
"
```

Pass criteria:
- `acquisition_date` in response exactly matches PostGIS value from Step B-1
- `sensor` matches

---

### Phase C: Threshold Mask Layer

**Goal:** Confirm problem mask tile is renderable and responds to threshold value.

**Test C-1: Default mask tile resolves**

From Phase A-2 response, open `layers.problem_mask.tile_url` in browser (replace `{z}/{x}/{y}` with a valid tile coordinate for the block's lat/lon, e.g., `10/848/545` for Indonesia region).

Pass criteria:
- Tile server returns HTTP 200 (not a GEE auth error or 404)
- Tile shows a colored overlay on at least part of the block (or is transparent if all pixels are healthy — acceptable if `problem_coverage_pct = 0`)

---

**Test C-2: Higher threshold increases coverage; lower threshold decreases it** *(conditional on FLAG-B = YES)*
```bash
curl -s -X GET "<VIEWER_URL>?block_id=18&threshold=0.7" -H "X-API-Key: <key>" \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('high threshold coverage:', r['stats']['problem_coverage_pct'])"

curl -s -X GET "<VIEWER_URL>?block_id=18&threshold=0.1" -H "X-API-Key: <key>" \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('low threshold coverage:', r['stats']['problem_coverage_pct'])"
```

Pass criteria:
- `threshold=0.7` produces strictly higher `problem_coverage_pct` than `threshold=0.1`
- Both requests return 200

---

### Phase D: Coverage Stat Sanity

**Goal:** Confirm stats are computationally valid and data_warning fires correctly.

**Test D-1: Coverage and NDVI values are in valid ranges**

From Phase A-2 response:

Pass criteria:
- `stats.problem_coverage_pct` is between 0.0 and 100.0 (inclusive)
- `stats.mean_ndvi` is between −1.0 and 1.0
- If FLAG-C = YES: `stats.problem_area_ha` is a positive float or null

---

**Test D-2: data_warning flag behavior** *(conditional on FLAG-G)*

Check `satellite_data` features for block 18:
```bash
docker compose exec postgis psql -U patcher -d canopysense_test \
  -c "SELECT cloud_cover, features->>'valid_pixel_ratio' FROM canopysense.satellite_data WHERE block_id=18"
```

If `cloud_cover > 30` or `valid_pixel_ratio < 0.7`:
- Pass criteria: `data_warning` in response is non-null string with a human-readable message
- Response still returns HTTP 200 (warning does not block)

If both values are within normal range:
- Pass criteria: `data_warning` is null

---

### Phase E: Performance Benchmark

**Goal:** Confirm response time ≤7s per PPX Q4 benchmark. Single block, single sensor.

```bash
for i in 1 2 3; do
  curl -s -o /dev/null -w "run $i: %{time_total}s\n" \
    -X GET "<VIEWER_URL>?block_id=18" -H "X-API-Key: <key>"
done
```

Pass criteria:
- All 3 runs complete in ≤7.0s
- Median ≤7.0s

Grading:
| Time | Result |
|------|--------|
| ≤7s | PASS |
| 7–10s | PARTIAL PASS — log for v0.13 optimization |
| >10s | FAIL — investigate `reduceRegion()` scale param and GEE collection filter width |

If FAIL: check that `acquisition_date` filter is tight (±1 day, not ±30 days) and `reduceRegion()` uses `bestEffort=True` with `maxPixels=1e7`.

---

### Phase F: Patcher and map_previewer Integrity

**Goal:** Confirm v0.12 changes did not break the patcher pipeline.

**Test F-1: patcher_cloud still returns v1.1 writes structure**
```bash
curl -s -X POST <PATCHER_URL> \
  -H "X-API-Key: <key>" \
  -H "Content-Type: application/json" \
  -d '{
    "api_version": "1.0",
    "blocks": {"type":"FeatureCollection","features":[{
      "type":"Feature",
      "geometry":{"type":"Polygon","coordinates":[[[108.0,-1.0],[108.1,-1.0],[108.1,-1.1],[108.0,-1.1],[108.0,-1.0]]]},
      "properties":{"block_id":18}
    }]}
  }' | python3 -c "
import sys,json
r=json.load(sys.stdin)
print('api_version:', r.get('api_version'))
print('has writes:', 'writes' in r)
print('has records (old):', 'records' in r)
"
```

Pass criteria:
- `api_version: "1.1"`
- `writes` present
- `records` absent at top level

---

**Test F-2: Line count integrity**
```bash
wc -l 03_Build/patcher_cloud_function.py 03_Build/patcher_local.py
```

Pass criteria:
- `patcher_cloud_function.py`: **254 lines**
- `patcher_local.py`: **300 lines**

---

**Test F-3: generate_preview() still writes HTML**

Run engine_launcher locally or check that existing `04_Test/result_output/` HTML output is still producible:
```bash
ls -la 04_Test/result_output/*.html 2>/dev/null || echo "No cached HTML — run engine locally to verify"
```

Pass criteria:
- Either existing HTML file present from a prior run, OR engine_launcher run locally produces `canopysense_visuals.html` without error
- No import error from `map_previewer.py` when `generate_preview()` is called

---

## 4. Observations & Output

*(Fill during execution)*

### Endpoint Contract
| Test | Result | Notes |
|------|--------|-------|
| A-1 Auth — 401 on missing key | PENDING | |
| A-2 Valid request — full structure | PENDING | |
| A-3 Unknown block — 404 | PENDING | |
| A-4 Missing block_id — 400 | PENDING | |
| A-5 No patch data — 404 | PENDING | |
| A-6 Invalid threshold — 400 | PENDING | FLAG-B conditional |

### Data Consistency
| Test | Result | Notes |
|------|--------|-------|
| B-1/B-2 acquisition_date matches PostGIS | PENDING | |

### Threshold Mask
| Test | Result | Notes |
|------|--------|-------|
| C-1 Default mask tile resolves | PENDING | |
| C-2 Threshold sensitivity | PENDING | FLAG-B conditional |

### Coverage Stat
| Test | Result | Notes |
|------|--------|-------|
| D-1 Coverage and NDVI in valid ranges | PENDING | |
| D-2 data_warning behavior | PENDING | FLAG-G conditional |

### Performance
| Test | Result | Notes |
|------|--------|-------|
| E-1 Response time ≤7s (3 runs) | PENDING | |

### Patcher Integrity
| Test | Result | Notes |
|------|--------|-------|
| F-1 patcher_cloud api_version 1.1 + writes | PENDING | |
| F-2 Line counts 254 / 300 | PENDING | |
| F-3 generate_preview() still works | PENDING | |

---

## 5. Success Criteria Summary

| Category | Criteria | Target | Result |
|----------|----------|--------|--------|
| **Auth** | 401 on missing key | Always | PENDING |
| **Contract** | Full layer + stat structure in 200 response | 100% | PENDING |
| **Data consistency** | `acquisition_date` exact match with `satellite_data` | Exact | PENDING |
| **Mask tile** | Both tile URLs return HTTP 200 from GEE tile server | 100% | PENDING |
| **Coverage stat** | Float in [0, 100]; mean_ndvi in [−1, 1] | Valid range | PENDING |
| **Performance** | Single block response time | ≤7s | PENDING |
| **Patcher unchanged** | api_version 1.1, writes present | Exact | PENDING |
| **Line integrity** | patcher_cloud 254 / patcher_local 300 | Exact | PENDING |
| **map_previewer backward compat** | generate_preview() still produces HTML | No regression | PENDING |

---

**ANT Sign-off**: PENDING — awaiting implementation.
