-- Migration 005: pipeline_trigger
-- Adds admin_pipeline_runs and admin_pipeline_schedules tables
-- for admin-initiated pipeline trigger and scheduling controls.
-- Run AFTER 004_admin_features.sql.

-- 1. admin_pipeline_runs: tracks every admin-triggered pipeline execution
CREATE TABLE IF NOT EXISTS admin_pipeline_runs (
    id              BIGSERIAL    PRIMARY KEY,
    run_id          UUID         NOT NULL UNIQUE,
    actor_id        BIGINT       NOT NULL REFERENCES users(id),
    mode            VARCHAR(20)  NOT NULL,
    company_id      BIGINT       REFERENCES companies(id),
    estate_id       INTEGER,
    afdeling_id     INTEGER,
    status          VARCHAR(20)  NOT NULL DEFAULT 'pending',
    date_start      VARCHAR(7),
    date_end        VARCHAR(7),
    sanitized_error TEXT,
    exit_code       INTEGER,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT admin_pipeline_runs_mode_check CHECK (
        mode IN ('scheduled', 'backfill')
    ),
    CONSTRAINT admin_pipeline_runs_status_check CHECK (
        status IN ('pending', 'running', 'succeeded', 'failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_admin_pipeline_runs_actor
    ON admin_pipeline_runs (actor_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_pipeline_runs_concurrency
    ON admin_pipeline_runs (status, mode, company_id, estate_id)
    WHERE status = 'running';

-- 2. admin_pipeline_schedules: recurring pipeline schedule config
CREATE TABLE IF NOT EXISTS admin_pipeline_schedules (
    id                  BIGSERIAL    PRIMARY KEY,
    created_by          BIGINT       NOT NULL REFERENCES users(id),
    mode                VARCHAR(20)  NOT NULL,
    company_id          BIGINT       REFERENCES companies(id),
    estate_id           INTEGER,
    afdeling_id         INTEGER,
    cadence             VARCHAR(20)  NOT NULL,
    timezone            VARCHAR(50)  NOT NULL DEFAULT 'UTC',
    date_start          VARCHAR(7),
    date_end            VARCHAR(7),
    enabled             BOOLEAN      NOT NULL DEFAULT TRUE,
    next_run            TIMESTAMPTZ,
    last_run            TIMESTAMPTZ,
    last_admin_run_id   BIGINT       REFERENCES admin_pipeline_runs(id),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT admin_pipeline_schedules_mode_check CHECK (
        mode IN ('scheduled', 'backfill')
    ),
    CONSTRAINT admin_pipeline_schedules_cadence_check CHECK (
        cadence IN ('daily', 'weekly', 'monthly')
    )
);

CREATE INDEX IF NOT EXISTS idx_admin_pipeline_schedules_due
    ON admin_pipeline_schedules (enabled, next_run)
    WHERE enabled = TRUE;
