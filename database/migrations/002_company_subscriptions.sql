-- Migration 002: company_subscriptions
-- Adds subscription tier table for raster serving mode routing.
-- Run AFTER schema.sql and seed.sql.
--
-- Tiers:
--   basic   → paid baseline service package; latest scene only, gee_mapid serving, no timelapse
--   premium → paid advanced service package; timelapse enabled, Maps Platform API
--
-- Subscription period (billing term) is separate from timelapse period (raster lookback):
--   billing_interval + subscription_starts_at + subscription_ends_at = commercial service period
--   timelapse_period_months = allowed raster lookback in months (NULL = latest only, basic)

CREATE TABLE IF NOT EXISTS company_subscriptions (
    id                      BIGSERIAL PRIMARY KEY,
    company_id              BIGINT REFERENCES companies(id) UNIQUE NOT NULL,
    tier                    VARCHAR(20)  NOT NULL DEFAULT 'basic'
                            CHECK (tier IN ('basic', 'premium')),
    status                  VARCHAR(20)  NOT NULL DEFAULT 'active'
                            CHECK (status IN ('trialing', 'active', 'past_due', 'cancelled', 'expired')),
    billing_interval        VARCHAR(20)  DEFAULT NULL
                            CHECK (billing_interval IN ('monthly', 'yearly', 'fixed_period')),
    subscription_starts_at  TIMESTAMP    DEFAULT NULL,
    subscription_ends_at    TIMESTAMP    DEFAULT NULL,
    timelapse_enabled       BOOLEAN      NOT NULL DEFAULT FALSE,
    timelapse_period_months INTEGER      DEFAULT NULL,
                            -- NULL = latest only (basic)
                            -- N    = lookback in months (premium)
    raster_serving_mode     VARCHAR(30)  NOT NULL DEFAULT 'gee_mapid'
                            CHECK (raster_serving_mode IN ('gee_mapid', 'maps_platform')),
    updated_at              TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_subscriptions_company
    ON company_subscriptions (company_id);

-- Seed: PT CanopySense Demo (company_id=1) → basic paid baseline
INSERT INTO company_subscriptions (
    company_id, tier, status, billing_interval,
    subscription_starts_at, subscription_ends_at,
    timelapse_enabled, timelapse_period_months, raster_serving_mode
)
VALUES (
    1, 'basic', 'active', 'yearly',
    '2026-01-01', '2026-12-31',
    FALSE, NULL, 'gee_mapid'
)
ON CONFLICT (company_id) DO NOTHING;

-- Seed: Geografi UI (company_id=2) → premium paid advanced, 3-month timelapse (testing)
INSERT INTO company_subscriptions (
    company_id, tier, status, billing_interval,
    subscription_starts_at, subscription_ends_at,
    timelapse_enabled, timelapse_period_months, raster_serving_mode
)
VALUES (
    2, 'premium', 'active', 'yearly',
    '2026-01-01', '2026-12-31',
    TRUE, 3, 'maps_platform'
)
ON CONFLICT (company_id) DO NOTHING;
