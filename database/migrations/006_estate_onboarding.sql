-- 006_estate_onboarding.sql
-- Stage 1.12: Admin Estate/Data Onboarding
--
-- 1. Makes canopysense.estates.geometry nullable so a metadata stub can be created
--    before blocks are imported. Existing rows with geometry stay committed.
-- 2. Recreates chk_estate_valid as null-aware (null geometry passes for drafts;
--    committed estates keep the ST_IsValid + SRID=4326 guarantee).
-- 3. Adds is_draft flag (TRUE = stub with no committed geometry).
-- 4. Makes canopysense.afdelings.geometry nullable for insert-then-compute pattern
--    during commit (insert afdeling with NULL, insert blocks, then union blocks).
-- 5. Recreates chk_afdeling_type as null-aware.
-- 6. Adds UNIQUE constraint on (afdelings.estate_id, afdelings.code) to enforce
--    hierarchy integrity and support afdeling upsert semantics during import commit.

BEGIN;

-- ─── canopysense.estates ─────────────────────────────────────────────────────

ALTER TABLE canopysense.estates ALTER COLUMN geometry DROP NOT NULL;

ALTER TABLE canopysense.estates DROP CONSTRAINT IF EXISTS chk_estate_valid;
ALTER TABLE canopysense.estates
    ADD CONSTRAINT chk_estate_valid
    CHECK (geometry IS NULL OR (ST_IsValid(geometry) AND ST_SRID(geometry) = 4326));

ALTER TABLE canopysense.estates
    ADD COLUMN IF NOT EXISTS is_draft BOOLEAN NOT NULL DEFAULT TRUE;

-- Backfill: estates that already have geometry are committed (not drafts)
UPDATE canopysense.estates SET is_draft = FALSE WHERE geometry IS NOT NULL;

-- ─── canopysense.afdelings ───────────────────────────────────────────────────

ALTER TABLE canopysense.afdelings ALTER COLUMN geometry DROP NOT NULL;

ALTER TABLE canopysense.afdelings DROP CONSTRAINT IF EXISTS chk_afdeling_type;
ALTER TABLE canopysense.afdelings
    ADD CONSTRAINT chk_afdeling_type
    CHECK (geometry IS NULL OR GeometryType(geometry) = 'MULTIPOLYGON');

-- UNIQUE (estate_id, code) enforces hierarchy integrity and is required for the
-- afdeling upsert (ON CONFLICT) used during import commit.
-- NOTE: This will fail if the existing DB has duplicate (estate_id, code) rows.
-- Fix any violations before running this migration.
ALTER TABLE canopysense.afdelings
    ADD CONSTRAINT uq_afdelings_estate_code UNIQUE (estate_id, code);

COMMIT;
