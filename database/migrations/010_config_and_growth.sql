-- 010_config_and_growth.sql
-- Stage 1.17: Company Configuration & Growth
--
-- Adds:
--   company_settings columns  — company_name, logo_path, show_name_in_header,
--                               show_logo_in_header, estate_change_status/timestamps,
--                               estate_change_file_path, estate_change_reject_reason
--   canopysense.estates       — is_active, archived_at
--   canopysense.afdelings     — is_active, archived_at
--   canopysense.blocks        — is_active, archived_at
--   canopysense.satellite_data — is_active, archived_at (schema completeness only;
--                               rows are NOT updated during archive due to append-only
--                               trigger; exclusion achieved via parent block is_active)
--   companies                 — reg_status
--   company_registration_requests table (new)

BEGIN;

-- ─── 0. Ensure company_settings has a unique constraint on company_id ────────
-- Required for ON CONFLICT (company_id) upsert pattern used by v1.17 endpoints.

CREATE UNIQUE INDEX IF NOT EXISTS uq_company_settings_company_id
    ON company_settings (company_id);

-- ─── 1. company_settings branding + estate change columns ────────────────────

ALTER TABLE company_settings
    ADD COLUMN IF NOT EXISTS company_name                VARCHAR(255)  DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS logo_path                   VARCHAR(500)  DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS show_name_in_header         BOOLEAN       NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS show_logo_in_header         BOOLEAN       NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS estate_change_status        VARCHAR(20)   NOT NULL DEFAULT 'NONE',
    ADD COLUMN IF NOT EXISTS estate_change_requested_at  TIMESTAMPTZ   DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS estate_change_file_path     VARCHAR(500)  DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS estate_change_reject_reason TEXT          DEFAULT NULL;

-- ─── 2. Archive columns on spatial tables ────────────────────────────────────

ALTER TABLE canopysense.estates
    ADD COLUMN IF NOT EXISTS is_active   BOOLEAN    NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_estates_is_active
    ON canopysense.estates (is_active) WHERE is_active = TRUE;

ALTER TABLE canopysense.afdelings
    ADD COLUMN IF NOT EXISTS is_active   BOOLEAN    NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_afdelings_is_active
    ON canopysense.afdelings (is_active) WHERE is_active = TRUE;

ALTER TABLE canopysense.blocks
    ADD COLUMN IF NOT EXISTS is_active   BOOLEAN    NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_blocks_is_active
    ON canopysense.blocks (is_active) WHERE is_active = TRUE;

-- satellite_data: columns added for schema completeness.
-- Rows are NOT writable during archive (append-only trigger prevents UPDATE).
-- Records become inaccessible when their parent block's is_active = false.
ALTER TABLE canopysense.satellite_data
    ADD COLUMN IF NOT EXISTS is_active   BOOLEAN    NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ DEFAULT NULL;

-- ─── 3. companies.reg_status ─────────────────────────────────────────────────

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS reg_status VARCHAR(20) NOT NULL DEFAULT 'active';

-- ─── 4. company_registration_requests ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS company_registration_requests (
    id           BIGSERIAL    PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    contact_name VARCHAR(150) NOT NULL,
    email        VARCHAR(150) NOT NULL,
    phone        VARCHAR(30)  DEFAULT NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'PENDING',
    reject_reason TEXT        DEFAULT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reg_requests_status
    ON company_registration_requests (status);

CREATE INDEX IF NOT EXISTS idx_reg_requests_email
    ON company_registration_requests (email);

COMMIT;
