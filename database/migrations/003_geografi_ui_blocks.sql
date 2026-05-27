-- Migration 003: Seed Geografi UI (company_id=2) with Sumbawa estate data
-- Director decision 2026-05-27: Geografi UI uses same Sumbawa AOI as company_id=1.
--
-- Safety policy (FMN 2026-05-27):
--   Existing seed uses explicit IDs — sequences must be synced before new inserts
--   to avoid stale-sequence duplicate key errors. No hardcoded IDs in this migration.
--   All steps are idempotent: ON CONFLICT for tables with UNIQUE, NOT EXISTS for afdelings.

-- Step 0: Advance sequences past highest existing IDs from seed explicit inserts.
SELECT setval(
    pg_get_serial_sequence('canopysense.estates', 'id'),
    MAX(id)
) FROM canopysense.estates;

SELECT setval(
    pg_get_serial_sequence('canopysense.afdelings', 'id'),
    MAX(id)
) FROM canopysense.afdelings;

SELECT setval(
    pg_get_serial_sequence('canopysense.blocks', 'id'),
    MAX(id)
) FROM canopysense.blocks;

-- Step 1: Estate for Geografi UI — copy geometry from company_id=1 estate.
-- ON CONFLICT (code) DO NOTHING: safe to re-run.
INSERT INTO canopysense.estates (company_id, name, code, geometry)
SELECT
    2,
    'Sumbawa Demo (Geografi UI)',
    'GEO-SBW',
    geometry
FROM canopysense.estates
WHERE company_id = 1
ON CONFLICT (code) DO NOTHING;

-- Step 2: Afdelings for Geografi UI — copy geometries from company_id=1 afdelings.
-- afdelings.code has no UNIQUE constraint, so use NOT EXISTS anti-join for idempotency.
INSERT INTO canopysense.afdelings (estate_id, company_id, name, code, geometry)
SELECT
    (SELECT id FROM canopysense.estates WHERE code = 'GEO-SBW'),
    2,
    a.name,
    'G-' || a.code,
    a.geometry
FROM canopysense.afdelings a
WHERE a.company_id = 1
  AND NOT EXISTS (
      SELECT 1
      FROM canopysense.afdelings x
      WHERE x.company_id = 2 AND x.code = 'G-' || a.code
  );

-- Step 3: Blocks for Geografi UI — copy geometries from company_id=1 blocks.
-- Block codes prefixed with 'G-', truncated to 20 chars for UNIQUE constraint.
-- ON CONFLICT (code) DO NOTHING: safe to re-run.
INSERT INTO canopysense.blocks (afdeling_id, company_id, name, code, geometry, plant_year, clone_type)
SELECT
    na.id,
    2,
    b.name,
    LEFT('G-' || b.code, 20),
    b.geometry,
    b.plant_year,
    b.clone_type
FROM canopysense.blocks b
JOIN canopysense.afdelings a  ON b.afdeling_id = a.id AND a.company_id = 1
JOIN canopysense.afdelings na ON na.code = 'G-' || a.code AND na.company_id = 2
WHERE b.company_id = 1
ON CONFLICT (code) DO NOTHING;
