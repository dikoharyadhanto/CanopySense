# Pending Plan — Production Raster Serving & Maps Platform Feasibility

Status: Non-official pending plan
Created: 2026-05-27
Owner Role: FMN advisory draft
Sigma State: Not registered in `progress.json`; not locked; not executable as DEV scope

## 1. Purpose

This pending plan exists to evaluate whether CanopySense should implement true production-grade raster tile serving through Google Maps Platform, a backend tile proxy, Cloud Optimized GeoTIFFs, or continue with Earth Engine `getMapId()` for the next product stage.

The immediate reason for this plan is the v1.6 decision that premium raster access is currently implemented as:

```text
premium entitlement = timelapse-capable getMapId
```

That is acceptable for v1.6 as long as it is documented honestly. It is not the same as true Maps Platform serving.

## 2. Timing Recommendation

This work is more realistic after or alongside online deployment preparation because it depends on:

- production secret management
- stable backend domain and routing
- service account / API key strategy
- usage logging
- cache and expiry policy
- rate limiting
- cost monitoring
- real browser/runtime tile request evidence

This plan should not block v1.6. It should inform v1.7, v1.8, or a later deployment/security stage.

## 3. Core Questions

| Question | Why It Matters |
| :--- | :--- |
| Should premium use real Maps Platform tile/session serving? | Determines architecture, cost, expiry, and cache design |
| Is `getMapId()` sufficient for Phase 1 deployed product? | Avoids unnecessary complexity if temporary URLs are acceptable |
| Should CanopySense proxy tiles through backend? | Protects credentials but may increase backend load |
| Should raster outputs be exported as GeoTIFF/COG? | More durable but requires storage and serving infrastructure |
| How should cache expiry be determined? | Prevents stale tiles and uncontrolled provider calls |
| How should cost be measured per company? | Required for premium pricing and operational guardrails |

## 4. Candidate Serving Models

| Model | Description | Pros | Risks |
| :--- | :--- | :--- | :--- |
| `getMapId()` only | Backend returns Earth Engine tile URL template | Simple, already working path, fast to integrate | Temporary URLs, expiry not programmatically exposed, less production-grade |
| Timelapse-capable `getMapId()` | Same serving as above, but premium can request historical windows | Good Phase 1 bridge; supports business entitlement | Must not be mislabeled as true Maps Platform |
| Maps Platform session/tile serving | Backend manages authenticated tile/session flow | Cleaner premium architecture if implemented correctly | More moving parts, cost/rate-limit implications, credential handling |
| Backend tile proxy | Frontend requests tiles from CanopySense backend; backend fetches provider tiles | Hides credentials and centralizes logging/cache | Backend bandwidth/load; needs careful cache policy |
| Exported GeoTIFF/COG | Generate durable raster artifacts, serve from object storage | Stable assets, easier long-term archival | Export jobs, storage, COG tiling, serving infra |
| Hybrid | Use `getMapId()` for latest/basic and COG/proxy for premium/history | Balanced path | More branching and operational complexity |

## 5. Recommended Evaluation Scope

This pending plan should be a feasibility and architecture decision plan, not a full implementation plan.

Recommended tasks:

| Task ID | Task | Output |
| :--- | :--- | :--- |
| P-TASK-001 | Audit provider options | Comparison of `getMapId`, Maps Platform, backend proxy, COG/GCS |
| P-TASK-002 | Define production raster serving requirements | Security, expiry, cache, cost, latency, UI behavior |
| P-TASK-003 | Identify required credentials and secrets | Service account/API key/env var strategy |
| P-TASK-004 | Design backend serving architecture | Endpoint shape and request flow |
| P-TASK-005 | Design cache and refresh policy | Cache key, TTL/expiry source, scheduled refresh rules |
| P-TASK-006 | Define cost and usage telemetry | Per-company usage log, cache hit/miss, provider calls |
| P-TASK-007 | Run controlled provider smoke if authorized | Sanitized evidence with real tile/session behavior |
| P-TASK-008 | Produce go/no-go recommendation | Decision for v1.7/v1.8/post-deployment |

## 6. Acceptance Criteria

| AC ID | Criteria | Required Result |
| :--- | :--- | :--- |
| P-AC-001 | Serving model options are compared honestly | Pros/cons and risks documented |
| P-AC-002 | Premium terminology is corrected | No false claim that v1.6 premium is true Maps Platform |
| P-AC-003 | Credential/security model is defined | Frontend never receives provider secrets |
| P-AC-004 | Cache policy is explicit | Expiry source, cache key, refresh policy, and invalidation documented |
| P-AC-005 | Cost model is measurable | Provider calls and cache hits can be tracked per company |
| P-AC-006 | Deployment dependency is clear | Work is tied to online deployment readiness if needed |
| P-AC-007 | Decision is actionable | Director can choose implement/defer/reject with evidence |

## 7. Recommended Architecture Direction

Short-term:

```text
Basic = paid latest-only getMapId
Premium = paid timelapse-capable getMapId
```

This is acceptable if docs and UI are honest about expiry.

Medium-term:

```text
Premium production serving = evaluated separately
```

Recommended candidates:

- backend tile/session endpoint
- provider reference cache
- per-company usage logging
- scheduled refresh for active premium companies
- rate limit / budget guard

Long-term:

```text
Durable raster archive = COG/GCS or equivalent
```

This is useful if CanopySense needs long-term historical raster products independent of transient Earth Engine tile URLs.

## 8. Non-Goals

This pending plan should not:

- block v1.6 Gate 3
- force real Maps Platform implementation before deployment readiness
- create billing/payment history tables
- expose credentials to frontend
- claim permanent tile URLs unless provider guarantees it
- replace the v1.6 raster engine contract

## 9. DEV Evidence Needed If Promoted

If this pending plan becomes an official Sigma Plan Doc, DEV should provide:

- provider documentation references
- architecture diagram or request-flow notes
- endpoint contract
- secret hygiene evidence
- cache policy evidence
- cost/usage estimate
- real smoke test only if Director authorizes credentials/quota
- clear limitation statement if real provider smoke is not run

## 10. Director Decision Points

| Decision | Options |
| :--- | :--- |
| When to promote this plan | Before v1.7, before v1.8, after deployment, or never |
| Premium serving target | Continue `getMapId`, true Maps Platform, proxy, COG/GCS, hybrid |
| Cost control strictness | Soft logging only, rate limits, hard quota, manual approval |
| Cache strategy | Lazy only, scheduled refresh, hybrid |
| Real provider smoke | Run now with credentials, defer until deployment, skip |

## 11. Current Recommendation

Keep v1.6 honest and limited:

```text
Premium v1.6 = timelapse-capable getMapId
True Maps Platform = pending feasibility / deployment-stage decision
```

Do not implement true Maps Platform until deployment, secret handling, cache, and usage logging are ready enough to produce meaningful evidence.
