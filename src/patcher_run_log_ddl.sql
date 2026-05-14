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
