-- ── Migration 002: Create restricted database user for Celery workers ──
-- 
-- Celery workers only need to read/write task-related tables and
-- update entity status fields. They should NOT have DDL permissions,
-- access to admin tables, or the ability to drop data.
--
-- Run this after the initial migration against your PostgreSQL database.
-- For SQLite, skip this — Celery relies on Redis for task results.
--
-- Usage:
--   psql -U operion -d operion -f database/migrations/002_create_celery_user.sql

-- ── Create restricted role ─────────────────────────────────────────────
-- The role has minimal privileges — only what Celery needs to function.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'operion_celery') THEN
        CREATE ROLE operion_celery WITH LOGIN PASSWORD 'CHANGE_ME_CELERY_PASSWORD';
    END IF;
END
$$;

-- ── Schema usage (must be granted explicitly per schema) ───────────────
GRANT USAGE ON SCHEMA public TO operion_celery;

-- ── Table-level permissions ────────────────────────────────────────────
-- Celery task results (Django Celery Results tables, if using the DB backend)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO operion_celery;

-- For celery-beat schedule tables (django_celery_beat)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO operion_celery;

-- ── Future tables ──────────────────────────────────────────────────────
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO operion_celery;

-- ── Sequence usage (for auto-increment columns) ────────────────────────
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO operion_celery;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO operion_celery;

-- ── Revoke destructive permissions explicitly (belt-and-suspenders) ────
REVOKE CREATE ON SCHEMA public FROM operion_celery;
REVOKE DROP ON ALL TABLES IN SCHEMA public FROM operion_celery;

-- ── Verify ─────────────────────────────────────────────────────────────
-- Connect as the new user and run: SELECT current_user, session_user;
-- You should see: operion_celery

-- ── Rollback ───────────────────────────────────────────────────────────
-- DROP ROLE IF EXISTS operion_celery;
