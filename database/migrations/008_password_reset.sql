-- 008_password_reset.sql
-- Stage 1.16: Forgot Password — adds password reset token columns to users.

BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS password_reset_token_hash      VARCHAR(255) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS password_reset_token_expires_at TIMESTAMPTZ  DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_users_reset_token_expires
    ON users (password_reset_token_expires_at)
    WHERE password_reset_token_expires_at IS NOT NULL;

COMMIT;
