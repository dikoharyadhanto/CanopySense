-- canopysense.patcher_run_log DDL (v1.3)
-- Run once on the contractor's local PostGIS to create the retry-memory table.
-- Idempotent: safe to re-run — CREATE TABLE IF NOT EXISTS.
-- For existing installations use patcher_run_log_migration_v1.3.sql instead.

CREATE TABLE IF NOT EXISTS canopysense.patcher_run_log (
    id                  SERIAL PRIMARY KEY,
    run_id              UUID NOT NULL,
    triggered_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at          TIMESTAMPTZ,                        -- set when batch begins (stale detection uses this)
    trigger_mode        TEXT NOT NULL,                      -- 'scheduled' | 'upload' | 'backfill'
    afdeling_id         INTEGER,                            -- NULL for upload trigger
    block_id            INTEGER,                            -- NULL for scheduled batches
    batch_fingerprint   TEXT,                               -- SHA-256 of sorted block_id list for this batch
    status              TEXT NOT NULL,                      -- 'IN_PROGRESS' | 'FULL_SUCCESS' | 'PARTIAL_SUCCESS' | 'FULL_FAILURE' | 'SKIPPED' | 'NO_NEW_DATA'
    rows_inserted       INTEGER DEFAULT 0,
    error_detail        TEXT,                               -- JSON: {"message": "...", "missing_block_ids": [...]}
    api_version         TEXT,
    estate_id           INTEGER,                            -- estate scope; NULL = all estates (scheduled default)
    date_start          DATE,                               -- window start for backfill chunks
    date_end            DATE,                               -- window end for backfill chunks

    CONSTRAINT patcher_run_log_status_check CHECK (
        status IN ('IN_PROGRESS', 'FULL_SUCCESS', 'PARTIAL_SUCCESS', 'FULL_FAILURE', 'SKIPPED', 'NO_NEW_DATA')
    ),
    CONSTRAINT patcher_run_log_trigger_mode_check CHECK (
        trigger_mode IN ('scheduled', 'upload', 'backfill')
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

-- Index for backfill window lookups
CREATE INDEX IF NOT EXISTS idx_patcher_run_log_backfill_window
    ON canopysense.patcher_run_log (trigger_mode, date_start, date_end)
    WHERE trigger_mode = 'backfill';
