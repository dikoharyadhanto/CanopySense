-- CanopySense local simulation — init.sql
-- Executed once by postgis container on first start.
-- Idempotent: safe to re-run against an existing database.

-- ============================================================
-- 1. Extensions and schemas
-- ============================================================
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS canopysense;
CREATE SCHEMA IF NOT EXISTS testschema;

-- ============================================================
-- 2. canopysense.blocks (read source for patcher_local.py)
-- ============================================================
CREATE TABLE IF NOT EXISTS canopysense.blocks (
    id           SERIAL PRIMARY KEY,
    code         TEXT NOT NULL,
    name         TEXT NOT NULL,
    afdeling_id  INTEGER NOT NULL,
    geometry     geometry(Polygon, 4326) NOT NULL
);

INSERT INTO canopysense.blocks (id, code, name, afdeling_id, geometry) VALUES
(1,  'BLK-001', 'Block 1',  1, ST_GeomFromText('POLYGON((107.0 -0.5, 107.1 -0.5, 107.1 -0.6, 107.0 -0.6, 107.0 -0.5))', 4326)),
(2,  'BLK-002', 'Block 2',  1, ST_GeomFromText('POLYGON((107.2 -0.5, 107.3 -0.5, 107.3 -0.6, 107.2 -0.6, 107.2 -0.5))', 4326)),
(3,  'BLK-003', 'Block 3',  1, ST_GeomFromText('POLYGON((107.4 -0.5, 107.5 -0.5, 107.5 -0.6, 107.4 -0.6, 107.4 -0.5))', 4326)),
(18, 'BLK-018', 'Block 18', 2, ST_GeomFromText('POLYGON((108.0 -1.0, 108.1 -1.0, 108.1 -1.1, 108.0 -1.1, 108.0 -1.0))', 4326))
ON CONFLICT (id) DO NOTHING;

-- Reset sequence so next auto-generated id does not collide with seed data.
SELECT setval(
    pg_get_serial_sequence('canopysense.blocks', 'id'),
    (SELECT MAX(id) FROM canopysense.blocks)
);

-- ============================================================
-- 3. canopysense.satellite_data (output table, starts empty)
-- ============================================================
CREATE TABLE IF NOT EXISTS canopysense.satellite_data (
    block_id         INTEGER        NOT NULL,
    acquisition_date DATE           NOT NULL,
    sensor           VARCHAR(20)    NOT NULL,
    cloud_cover      FLOAT,
    ndvi             FLOAT,
    evi              FLOAT,
    ndre             FLOAT,
    savi             FLOAT,
    gndvi            FLOAT,
    features         JSONB,
    PRIMARY KEY (block_id, acquisition_date, sensor)
);

-- ============================================================
-- 4. canopysense.patcher_run_log
--    Verbatim from 03_Build/patcher_run_log_ddl.sql (v0.9)
-- ============================================================

-- canopysense.patcher_run_log DDL (v0.9)
-- Run once on the contractor's local PostGIS to create the retry-memory table.
-- Idempotent: safe to re-run — CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS canopysense.patcher_run_log (
    id                  SERIAL PRIMARY KEY,
    run_id              UUID NOT NULL,
    triggered_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at          TIMESTAMPTZ,                        -- set when batch begins (stale detection uses this)
    trigger_mode        TEXT NOT NULL,                      -- 'scheduled' | 'upload'
    afdeling_id         INTEGER,                            -- NULL for upload trigger
    block_id            INTEGER,                            -- NULL for scheduled batches
    batch_fingerprint   TEXT,                               -- SHA-256 of sorted block_id list for this batch
    status              TEXT NOT NULL,                      -- 'IN_PROGRESS' | 'FULL_SUCCESS' | 'PARTIAL_SUCCESS' | 'FULL_FAILURE' | 'SKIPPED'
    rows_inserted       INTEGER DEFAULT 0,
    error_detail        TEXT,                               -- JSON: {"message": "...", "missing_block_ids": [...]}
    api_version         TEXT,

    CONSTRAINT patcher_run_log_status_check CHECK (
        status IN ('IN_PROGRESS', 'FULL_SUCCESS', 'PARTIAL_SUCCESS', 'FULL_FAILURE', 'SKIPPED')
    ),
    CONSTRAINT patcher_run_log_trigger_mode_check CHECK (
        trigger_mode IN ('scheduled', 'upload')
    )
);

-- Index for the retry query: find FULL_FAILURE + PARTIAL_SUCCESS batches for scheduled runs
CREATE INDEX IF NOT EXISTS idx_patcher_run_log_retry
    ON canopysense.patcher_run_log (trigger_mode, afdeling_id, status)
    WHERE trigger_mode = 'scheduled';

-- Index for IN_PROGRESS guard: fast lookup by afdeling + status
CREATE INDEX IF NOT EXISTS idx_patcher_run_log_in_progress
    ON canopysense.patcher_run_log (trigger_mode, afdeling_id, started_at)
    WHERE status = 'IN_PROGRESS';

-- ============================================================
-- 5. canopysense.patcher_write_test (Phase D forward-compat, starts empty)
-- ============================================================
CREATE TABLE IF NOT EXISTS canopysense.patcher_write_test (
    block_id         INTEGER     NOT NULL,
    acquisition_date DATE        NOT NULL,
    sensor           VARCHAR(20) NOT NULL,
    test_value       TEXT,
    PRIMARY KEY (block_id, acquisition_date, sensor)
);

-- ============================================================
-- 6. testschema mirrors (Phase C custom schema test, start empty)
-- ============================================================
CREATE TABLE IF NOT EXISTS testschema.satellite_data (LIKE canopysense.satellite_data INCLUDING ALL);
CREATE TABLE IF NOT EXISTS testschema.patcher_run_log (LIKE canopysense.patcher_run_log INCLUDING ALL);
