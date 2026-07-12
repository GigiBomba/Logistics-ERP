#!/bin/bash
# Automated PostgreSQL backup script
# Usage: ./scripts/backup_db.sh
# Schedule via cron: 0 2 * * * /path/to/scripts/backup_db.sh

BACKUP_DIR="${BACKUP_DIR:-./data/backups}"
DB_NAME="${OPERION_DB_NAME:-operion}"
DB_USER="${OPERION_DB_USER:-operion}"
DB_HOST="${OPERION_DB_HOST:-localhost}"
DB_PORT="${OPERION_DB_PORT:-5432}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/operion_backup_${TIMESTAMP}.sql.gz"

echo "[$(date)] Starting backup to $BACKUP_FILE"

PGPASSWORD="${OPERION_DB_PASSWORD}" pg_dump \
    -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --no-owner --no-acl | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "[$(date)] Backup successful: $(du -h "$BACKUP_FILE" | cut -f1)"

    # Clean up old backups
    find "$BACKUP_DIR" -name "operion_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete
    echo "[$(date)] Cleaned up backups older than $RETENTION_DAYS days"
else
    echo "[$(date)] BACKUP FAILED!" >&2
    exit 1
fi
