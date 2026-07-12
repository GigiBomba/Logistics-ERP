#!/bin/bash
# ── PostgreSQL initialization script ─────────────────────────────────
# Runs automatically when the PostgreSQL container starts for the first time.
# Creates the restricted Celery user with minimal privileges.
#
# See: https://hub.docker.com/_/postgres/#initialization-scripts

set -e

echo "[init-db] Creating restricted Celery user..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'operion_celery') THEN
            CREATE ROLE operion_celery WITH LOGIN PASSWORD '${OPERION_CELERY_PASSWORD:-CHANGE_ME_CELERY_PASSWORD}';
        END IF;
    END
    \$\$;

    GRANT USAGE ON SCHEMA public TO operion_celery;
    GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO operion_celery;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE ON TABLES TO operion_celery;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO operion_celery;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT USAGE ON SEQUENCES TO operion_celery;

    REVOKE CREATE ON SCHEMA public FROM operion_celery;
EOSQL

echo "[init-db] Celery user created successfully."
