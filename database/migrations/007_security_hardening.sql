-- 007_security_hardening.sql
-- Stage 1.14: Security Hardening — New Device Detection tables
--
-- Adds:
--   canopysense.known_devices       — stores hashed device tokens for admin/super-admin
--   canopysense.device_otp_sessions — stores single-use OTP sessions for device verification

BEGIN;

-- ─── known_devices ────────────────────────────────────────────────────────────
-- Stores a SHA-256 hash of each recognized device token per admin/super-admin user.
-- Raw device token lives only in the client's HttpOnly cookie — never in this table.

CREATE TABLE IF NOT EXISTS canopysense.known_devices (
    id            SERIAL      PRIMARY KEY,
    user_id       INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_hash   TEXT        NOT NULL UNIQUE,
    device_label  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_known_devices_user_id
    ON canopysense.known_devices (user_id);

-- ─── device_otp_sessions ─────────────────────────────────────────────────────
-- Stores bcrypt-hashed single-use OTP codes issued during new-device login.
-- Sessions expire after 10 minutes; used=TRUE prevents replay.

CREATE TABLE IF NOT EXISTS canopysense.device_otp_sessions (
    id             SERIAL      PRIMARY KEY,
    user_id        INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    otp_hash       TEXT        NOT NULL,
    otp_expires_at TIMESTAMPTZ NOT NULL,
    resend_count   INTEGER     NOT NULL DEFAULT 0,
    used           BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_device_otp_sessions_user_id
    ON canopysense.device_otp_sessions (user_id);

COMMIT;
