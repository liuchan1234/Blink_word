-- ══════════════════════════════════════════════
-- Migration 005: Add is_premium flag to users
-- ══════════════════════════════════════════════

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_premium BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN users.is_premium IS 'True if user has an active paid membership';
