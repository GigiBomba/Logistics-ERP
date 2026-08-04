# SQLite database backup script
# Scheduled daily via Windows Task Scheduler

param(
    [string]$DataDir = "C:\Users\Bonjo\source\repos\Calculator logistica\data",
    [string]$BackupDir = "C:\Users\Bonjo\source\repos\Calculator logistica\data\backups",
    [int]$RetentionDays = 30
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dbPath = Join-Path $DataDir "cashflow.db"

# Ensure backup directory exists
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

# Check source DB exists
if (-not (Test-Path $dbPath)) {
    Write-Error "Database not found: $dbPath"
    exit 1
}

# Create backup with timestamp
$backupPath = Join-Path $BackupDir "cashflow_backup_$timestamp.db"
Copy-Item -Path $dbPath -Destination $backupPath -Force

# Verify backup
if (Test-Path $backupPath) {
    $srcSize = (Get-Item $dbPath).Length
    $bakSize = (Get-Item $backupPath).Length
    Write-Output "Backup created: $backupPath"
    Write-Output "Source size: $srcSize bytes"
    Write-Output "Backup size: $bakSize bytes"
} else {
    Write-Error "Backup failed — file not created"
    exit 1
}

# Cleanup backups older than retention period
$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $BackupDir -Filter "cashflow_backup_*.db" | Where-Object {
    $_.LastWriteTime -lt $cutoff
} | Remove-Item -Force

Write-Output "Backup complete. Old backups cleaned (retention: $RetentionDays days)."
