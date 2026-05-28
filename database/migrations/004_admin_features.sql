-- Migration 004: admin_features
-- Adds is_admin flag, first-login setup-token fields to users,
-- and admin_audit_log append-only table.
-- Run AFTER 003 (if present) or after 002_company_subscriptions.sql.

-- 1. Add is_admin column (False for all existing users by default)
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Add first-login setup token fields
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS setup_required        BOOLEAN   NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS setup_token_hash      VARCHAR(255)       DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS setup_token_expires_at TIMESTAMP         DEFAULT NULL;

-- 3. Admin audit log (append-only enforced by trigger)
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id          BIGSERIAL    PRIMARY KEY,
    actor_id    BIGINT       NOT NULL REFERENCES users(id),
    action      VARCHAR(100) NOT NULL,
    target_type VARCHAR(50)  NOT NULL,
    target_id   BIGINT,
    metadata    JSONB        DEFAULT '{}',
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_actor
    ON admin_audit_log (actor_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_audit_target
    ON admin_audit_log (target_type, target_id, created_at DESC);

-- Trigger: admin_audit_log is append-only — no UPDATE or DELETE
CREATE OR REPLACE FUNCTION prevent_admin_audit_log_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'admin_audit_log is append-only. Updates and deletes are not permitted.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS immutable_admin_audit_log ON admin_audit_log;
CREATE TRIGGER immutable_admin_audit_log
    BEFORE UPDATE OR DELETE ON admin_audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_admin_audit_log_mutation();
