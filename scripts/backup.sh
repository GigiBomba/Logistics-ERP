#!/usr/bin/env bash
# ── Operion ERP Database Backup Script ──────────────────────────────
# Usage:
#   ./scripts/backup.sh                    # interactive (prompts for password)
#   OPERION_DB_PASSWORD=secret ./scripts/backup.sh  # non-interactive
#
# Schedules:
#   Add to crontab for daily backups:
#     0 3 * * * /opt/operion/scripts/backup.sh >> /var/log/operion/backup.log 2>&1
#
# Restore:
#   gunzip -c backup_2026-07-11.sql.gz | psql -U operion -d operion

set -euo pipefail

# ── Configuration ───────────────────────────────────────────────────
BACKUP_DIR="${OPERION_BACKUP_DIR:-/app/backups}"
DB_NAME="${OPERION_DB_NAME:-operion}"
DB_USER="${OPERION_DB_USER:-operion}"
DB_HOST="${OPERION_DB_HOST:-localhost}"
DB_PORT="${OPERION_DB_PORT:-5432}"
DB_PASSWORD="${OPERION_DB_PASSWORD:-}"
RETENTION_DAYS="${OPERION_BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# ── Dependencies ────────────────────────────────────────────────────
for cmd in pg_dump gzip find mkdir; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: Required command '$cmd' not found. Install it and retry." >&2
        exit 1
    fi
done

# ── Ensure backup directory exists ──────────────────────────────────
mkdir -p "$BACKUP_DIR"

# ── Build connection string ─────────────────────────────────────────
export PGPASSWORD="$DB_PASSWORD"
CONN_OPTS="-h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"

# ── Dump ────────────────────────────────────────────────────────────
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting backup of $DB_NAME..."
if pg_dump $CONN_OPTS --no-owner --no-privileges | gzip > "$BACKUP_FILE"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup complete: $BACKUP_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BACKUP FAILED" >&2
    exit 1
fi

# ── Retention: delete backups older than RETENTION_DAYS ─────────────
find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -type f -mtime "+$RETENTION_DAYS" -delete
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleaned up backups older than ${RETENTION_DAYS} days."

# ── Validate: check the backup is non-empty and valid gzip ──────────
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: Backup file $BACKUP_FILE failed integrity check" >&2
    exit 1
fi
BACKUP_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Integrity check passed. Size: ${BACKUP_SIZE} bytes."

# ── Optional: upload to R2 / S3 ─────────────────────────────────────
# Configure these environment variables for off-site backup storage:
#   AWS_ACCESS_KEY_ID=<R2-token-id>
#   AWS_SECRET_ACCESS_KEY=<R2-token-secret>
#   AWS_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
#   AWS_DEFAULT_REGION=auto
if command -v aws &>/dev/null && [ -n "${AWS_ACCESS_KEY_ID:-}" ] && [ -n "${AWS_ENDPOINT_URL:-}" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Uploading to R2/S3..."
    if aws s3 cp "$BACKUP_FILE" "s3://operion-backups/${DB_NAME}_${TIMESTAMP}.sql.gz" --endpoint-url "$AWS_ENDPOINT_URL" 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Uploaded to R2 successfully."
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: R2 upload failed (non-fatal)" >&2
    fi
fi
