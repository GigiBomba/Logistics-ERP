-- ── Migration: Per-partner API key management ─────────────────────────
--
-- Replaces the single global OPERION_API_KEY with scoped, per-partner
-- API keys that support rotation, expiry, and usage tracking.
--
-- The table is also defined in database/schema.py and created automatically
-- on startup. This migration file exists for standalone / manual setups.
--
-- Applied automatically via DatabaseManager._create_tables_and_indices().
-- Manual usage:
--   sqlite3 data/cashflow.db < database/migrations/api_keys.sql

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL UNIQUE,        -- SHA-256 hash of the actual key
    key_prefix TEXT NOT NULL,             -- First 12 chars for identification (e.g., "ok_tim_ab12")
    name TEXT NOT NULL,                   -- Human-readable name (e.g., "TIMOCOM Production")
    partner TEXT NOT NULL,                -- Partner identifier (e.g., "timocom")
    scopes TEXT DEFAULT '[]',            -- JSON array of allowed scopes
    is_active INTEGER DEFAULT 1,
    created_by INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    last_used_at TEXT,
    expires_at TEXT,
    revoked_at TEXT,
    company_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_api_keys_partner ON api_keys(partner);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active);
