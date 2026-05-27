# CanopySense Subscription Model Recommendation

Date: 2026-05-27
Status: Director advisory note for development planning

## 1. Summary

CanopySense should treat subscription as a company-level commercial contract, not a user-level feature toggle. The product is a B2B plantation intelligence web app, so pricing should be based primarily on estate/company access, raster capability, historical/timelapse access, service period, and operational support.

For the current development phase, use only two tiers:

- `basic`
- `premium`

Do not interpret `basic` as free. In CanopySense, `basic` means a paid baseline web-app service package with a simpler data capability and likely a longer fixed-cost service period. `premium` means a higher-value package with timestamp/timelapse raster access and potentially higher operating cost.

## 2. Recommended Tier Model

| Tier | Commercial Meaning | Raster Capability | Intended Buyer |
| :--- | :--- | :--- | :--- |
| `basic` | Paid baseline service package | Latest raster only, no timelapse | Client that needs current estate monitoring without historical exploration |
| `premium` | Paid advanced service package | Latest raster plus timestamp/timelapse access | Client that needs historical comparison, anomaly investigation, and richer map analysis |

Enterprise/custom tiers should be deferred. They may become useful later for large estates, custom reporting, SLA, integrations, dedicated onboarding, or multi-company groups, but adding them now would increase schema and UI complexity too early.

## 3. Pricing Logic

CanopySense should avoid pricing only by number of users. The value of the product is tied more closely to monitored land and data capability than to seats.

Recommended pricing factors:

| Factor | Why It Matters |
| :--- | :--- |
| Company/estate subscription | One company maps to one estate in the current product direction |
| Estate area | Larger areas increase data processing, user value, and support complexity |
| Raster serving mode | `maps_platform`/premium access may carry higher operational cost |
| Timelapse period | Longer historical lookback is higher value and may increase compute/API usage |
| Billing interval | Monthly/yearly/fixed-period packages affect cash flow and renewal handling |
| Support/onboarding | B2B clients may need setup, training, and periodic review |

Early commercial packaging can be simple:

- Basic: fixed paid web-app service for a defined period, latest-only raster.
- Premium: higher paid service, includes timelapse raster access for a configured period.

## 4. Subscription Data Model

Subscription access should be stored at company level.

Recommended `company_subscriptions` fields:

| Field | Recommended Type / Values | Purpose |
| :--- | :--- | :--- |
| `company_id` | FK to `companies(id)` | Company-level subscription authority |
| `tier` | `basic`, `premium` | Commercial package |
| `status` | `trialing`, `active`, `past_due`, `cancelled`, `expired` | Whether access should be active |
| `billing_interval` | `monthly`, `yearly`, `fixed_period` | Commercial billing period |
| `subscription_starts_at` | timestamp/date | Contract/service start |
| `subscription_ends_at` | timestamp/date/null | Contract/service end or renewal boundary |
| `timelapse_enabled` | boolean | Whether historical/timelapse raster is enabled |
| `timelapse_period_months` | integer/null | Allowed raster lookback in months |
| `raster_serving_mode` | `gee_mapid`, `maps_platform` | Technical serving route |
| `updated_at` | timestamp | Audit/update trace |

Use `timelapse_period_months`, not `timestamp_period`. The field controls allowed historical lookback for raster timelapse, and the unit should be explicit.

## 5. Basic Tier Clarification

`basic` is paid. It should not be treated as a free tier in code, UI, docs, or tests.

Recommended interpretation:

- Paid fixed-cost access to the CanopySense web app.
- Longer service period is acceptable, such as yearly or custom fixed period.
- Latest raster only.
- No timestamp selector.
- No timelapse/history slider.
- Lower operational cost and simpler support path.

This framing avoids weakening the product's perceived value. The distinction is not paid vs free; it is baseline paid service vs advanced paid service.

## 6. Premium Tier Clarification

`premium` is also paid, with higher value and higher capability.

Recommended interpretation:

- Includes timestamp/timelapse raster access.
- Uses `maps_platform` serving mode if needed by the implementation.
- Has a configured `timelapse_period_months`, starting with 3 months for testing.
- Can later be upgraded to longer lookback periods as commercial add-ons.

Future premium add-ons could include 6-month/12-month history, export reports, alerting, scheduled review, and advanced analytics.

## 7. Payment History Scope

Do not implement full payment history in the raster-engine phase unless explicitly approved as a billing/admin plan.

Reason:

- v1.6 should prove raster engine and subscription access control.
- Payment history adds billing workflows, invoice lifecycle, provider integration, refunds, and admin UI.
- Those are important, but they are not required to determine raster access in the current development phase.

When billing/admin scope opens, add a separate table such as `subscription_payments`.

Suggested future `subscription_payments` fields:

| Field | Purpose |
| :--- | :--- |
| `company_id` | Company that paid |
| `subscription_id` | Related subscription row |
| `amount` | Paid or invoiced amount |
| `currency` | Billing currency |
| `payment_status` | `pending`, `paid`, `failed`, `refunded`, `void` |
| `billing_period_start` | Covered period start |
| `billing_period_end` | Covered period end |
| `paid_at` | Payment timestamp |
| `provider` | Manual, Stripe, Paddle, bank transfer, etc. |
| `provider_invoice_id` | External invoice/payment reference |

Payment history should be audit evidence, not the direct feature-access authority. Raster access should depend on `company_subscriptions.status`, `tier`, `subscription_ends_at`, `timelapse_enabled`, and `timelapse_period_months`.

## 8. Access-Control Rule

Backend must be the authority for subscription access.

Rules:

- Frontend may display subscription context, but must not decide paid feature access.
- JWT may include display context, but must not be trusted as billing authority.
- Raster API must query `company_subscriptions` for the user's company before choosing serving mode.
- Basic users must not receive premium timelapse behavior by adding a date parameter manually.
- Expired or inactive subscriptions should return a clear subscription/access error, not silently downgrade unless that policy is intentionally chosen.

## 9. Raster Cache And Cost-Control Recommendation

Raster caching should be treated as a core cost-control mechanism. The app should avoid regenerating raster tile/session references for every user request when another user in the same company has already requested the same raster product.

Cache should be company-scoped, not user-scoped.

Recommended cache key:

```text
company_id:index_name:acquisition_date:bounds_hash:palette_hash:serving_mode
```

Recommended cache behavior:

- Check subscription status first.
- Check cache before calling Earth Engine, Maps Platform, or any external provider.
- Return cached raster metadata/session/reference when it is still valid.
- Generate a new provider reference only when cache is missing, expired, invalid, or the requested raster product changed.
- Use a lock or single-flight mechanism so concurrent users do not trigger duplicate generation for the same cache key.
- Store provider `expires_at` or effective HTTP cache expiry; do not hardcode 14 days or 48 hours as a permanent assumption.
- Refresh scheduled cache only for active subscriptions and useful raster products.
- Log cache hit/miss per company for cost analysis.

Recommended cache table:

```text
raster_tile_cache
- company_id
- index_name
- acquisition_date
- serving_mode
- cache_key
- provider_ref
- tile_url_template
- metadata_json
- generated_at
- expires_at
- last_accessed_at
- generation_status
```

The safest cache target is metadata/session/reference, not bulk stored Google tile images. Any tile/image caching must follow provider terms and response cache headers. Google Maps Tile API content should not be pre-fetched, stored, or cached except where the applicable terms and `Cache-Control` headers allow it.

For Basic:

- Cache only latest raster products needed by the web app.
- Keep latest-only behavior simple and cheap.
- Regenerate only when the provider reference expires or the source raster changes.

For Premium:

- Cache by company, index, acquisition date, and serving mode.
- Respect `timelapse_period_months`.
- Avoid pre-generating every historical date unless scheduled cost has been evaluated.
- Prefer lazy generation plus scheduled refresh for recent/popular products.

Cost-control rule:

```text
subscription check -> cache lookup -> cache hit return -> cache miss generate once -> store expiry -> return
```

This avoids a bad pattern where multiple users in the same premium company each trigger new provider calls for the same map state.

## 10. Recommended v1.6 Scope

For v1.6, implement only what is needed to support raster access control:

- `basic` and `premium` tiers only.
- `company_subscriptions` table.
- `timelapse_period_months`.
- `billing_interval`.
- `subscription_starts_at`.
- `subscription_ends_at`.
- `status`.
- Basic routing to `gee_mapid`.
- Premium routing to `maps_platform`.
- Backend subscription check before raster metadata/tile response.
- Company-scoped raster metadata/reference cache, if the raster endpoint is implemented in this phase.
- No full payment history implementation.
- No billing provider integration.
- No billing admin UI.

## 11. Follow-Up Plan Candidates

Potential future plans:

| Plan Area | Scope |
| :--- | :--- |
| Billing/admin foundation | Payment history, invoice records, manual subscription management |
| Provider integration | Stripe/Paddle/manual invoice workflow |
| Super admin subscription UI | Create/edit company subscription, status, billing interval, expiry |
| Premium add-ons | Longer timelapse period, export/report, alerts |
| Raster cost controls | Cache dashboard, per-company usage limits, quota alerts, scheduled refresh policy |
| Commercial analytics | Revenue, active subscriptions, renewal reminders |

## 12. Decision Recommendation

Recommended decision for current development:

1. Keep only `basic` and `premium`.
2. Treat both as paid tiers.
3. Define `basic` as paid baseline service, not free.
4. Use `timelapse_period_months` for raster lookback.
5. Use `billing_interval`, `subscription_starts_at`, and `subscription_ends_at` for subscription term.
6. Defer payment history to a billing/admin plan.
7. Keep backend DB subscription check as the only authority for raster access.
8. Cache raster metadata/session/reference per company to avoid duplicate provider calls across users.
9. Use provider expiry/headers as the cache limit, not a fixed assumption.
