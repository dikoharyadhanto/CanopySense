-- 009_role_and_members.sql
-- Stage 1.16: Role column migration + member management support
--
-- Adds:
--   users.role                      — canonical RBAC column (super_admin | admin | manager | viewer | null)
--   users.viewer_invite_token_hash  — hashed invite token for viewer invitations
--   users.viewer_invite_token_expires_at
--   users.leave_request_status      — PENDING | APPROVED | REJECTED | null
--   company_settings columns        — timezone, notify_pipeline_failure, notify_pipeline_success

BEGIN;

-- ─── 1. role column on users ──────────────────────────────────────────────────

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT NULL;

-- Backfill from existing is_admin + company_id state:
--   is_global_admin = TRUE               → super_admin
--   is_admin = TRUE AND company_id set   → admin
--   is_admin = FALSE AND company_id set  → manager
--   everything else                      → NULL (unaffiliated)
UPDATE users
SET role = CASE
    WHEN is_global_admin = TRUE THEN 'super_admin'
    WHEN is_admin = TRUE AND company_id IS NOT NULL THEN 'admin'
    WHEN is_admin = FALSE AND company_id IS NOT NULL THEN 'manager'
    ELSE NULL
END
WHERE role IS NULL;

CREATE INDEX IF NOT EXISTS idx_users_role ON users (role) WHERE role IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_company_id ON users (company_id) WHERE company_id IS NOT NULL;

-- ─── 2. viewer invite token columns on users ──────────────────────────────────

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS viewer_invite_token_hash      VARCHAR(255) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS viewer_invite_token_expires_at TIMESTAMPTZ  DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS leave_request_status           VARCHAR(20)  DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_users_viewer_invite_expires
    ON users (viewer_invite_token_expires_at)
    WHERE viewer_invite_token_expires_at IS NOT NULL;

-- ─── 3. company_settings notification/timezone columns ───────────────────────
-- company_settings already exists (branding: app_title, logo_url, theme_id, custom_css).
-- Add notification and timezone columns without touching existing columns.

ALTER TABLE company_settings
    ADD COLUMN IF NOT EXISTS timezone                  VARCHAR(50)  DEFAULT 'Asia/Jakarta',
    ADD COLUMN IF NOT EXISTS notify_pipeline_failure   BOOLEAN      NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS notify_pipeline_success   BOOLEAN      NOT NULL DEFAULT FALSE;

COMMIT;
