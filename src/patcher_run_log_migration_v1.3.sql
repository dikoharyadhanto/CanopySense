-- patcher_run_log_migration_v1.3.sql
-- Safe ALTER TABLE migration for existing CanopySense installations (patcher_run_log v0.9 → v1.3).
-- Idempotent: uses ADD COLUMN IF NOT EXISTS and safe constraint extension pattern.
-- Run ONCE on the contractor's local PostGIS before deploying patcher_local v1.3.

BEGIN;

-- 1. Add new columns (nullable — no impact on existing rows)
ALTER TABLE canopysense.patcher_run_log
    ADD COLUMN IF NOT EXISTS estate_id  INTEGER,
    ADD COLUMN IF NOT EXISTS date_start DATE,
    ADD COLUMN IF NOT EXISTS date_end   DATE;

-- 2. Extend trigger_mode CHECK to include 'backfill'
--    PostgreSQL does not support ALTER CONSTRAINT, so we drop and recreate.
ALTER TABLE canopysense.patcher_run_log
    DROP CONSTRAINT IF EXISTS patcher_run_log_trigger_mode_check;

ALTER TABLE canopysense.patcher_run_log
    ADD CONSTRAINT patcher_run_log_trigger_mode_check CHECK (
        trigger_mode IN ('scheduled', 'upload', 'backfill')
    );

-- 3. Extend status CHECK to include 'NO_NEW_DATA'
ALTER TABLE canopysense.patcher_run_log
    DROP CONSTRAINT IF EXISTS patcher_run_log_status_check;

ALTER TABLE canopysense.patcher_run_log
    ADD CONSTRAINT patcher_run_log_status_check CHECK (
        status IN ('IN_PROGRESS', 'FULL_SUCCESS', 'PARTIAL_SUCCESS', 'FULL_FAILURE', 'SKIPPED', 'NO_NEW_DATA')
    );

-- 4. Add backfill window index
CREATE INDEX IF NOT EXISTS idx_patcher_run_log_backfill_window
    ON canopysense.patcher_run_log (trigger_mode, date_start, date_end)
    WHERE trigger_mode = 'backfill';

-- 5. backfill_skipped: add batch_fp column for scope-aware resume guard
--    Only applies if the table already exists from an earlier v1.3 deployment.
--    Fresh installations get the correct DDL from _ensure_backlog_table() at runtime.
ALTER TABLE IF EXISTS canopysense.backfill_skipped
    ADD COLUMN IF NOT EXISTS batch_fp TEXT NOT NULL DEFAULT '';

-- Replace old 2-column unique with scope-aware 3-column unique (idempotent)
ALTER TABLE IF EXISTS canopysense.backfill_skipped
    DROP CONSTRAINT IF EXISTS backfill_skipped_window_start_window_end_key;

ALTER TABLE IF EXISTS canopysense.backfill_skipped
    DROP CONSTRAINT IF EXISTS backfill_skipped_window_start_window_end_batch_fp_key;

ALTER TABLE IF EXISTS canopysense.backfill_skipped
    ADD CONSTRAINT backfill_skipped_window_start_window_end_batch_fp_key
    UNIQUE (window_start, window_end, batch_fp);

COMMIT;
