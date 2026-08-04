# Start Docker test infrastructure (PostgreSQL + Redis) for Operion ERP integration tests.
# This script is triggered by Windows Task Scheduler at user logon.

$ErrorActionPreference = "SilentlyContinue"
$logFile = "$env:USERPROFILE\.slim\docker-test-services.log"
$projectDir = "C:\Users\Bonjo\source\repos\Calculator logistica"

Start-Transcript -Path $logFile -Append

Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting Docker test services..."

# 1. Ensure Docker Desktop is running
$dockerProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerProcess) {
    Write-Output "  Starting Docker Desktop..."
    Start-Process -FilePath "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    # Wait up to 60 seconds for Docker to be ready
    $wait = 0
    do {
        Start-Sleep -Seconds 3
        $wait += 3
        $ok = docker ps 2>$null
    } while ($LASTEXITCODE -ne 0 -and $wait -lt 60)
    if ($LASTEXITCODE -ne 0) {
        Write-Output "  FAILED: Docker did not start within 60s"
        Stop-Transcript
        exit 1
    }
    Write-Output "  Docker Desktop ready ($wait seconds)"
}

# 2. Start or ensure PostgreSQL + Redis containers are running
Set-Location $projectDir
$composeFile = "docker-compose.test.yml"
$composeResult = docker compose -f $composeFile up -d 2>&1
Write-Output "  Compose result: $composeResult"

# 3. Verify
$psql = docker ps --filter "name=postgres-test" --format "{{.Names}} {{.Status}}" 2>&1
$redis = docker ps --filter "name=redis-test" --format "{{.Names}} {{.Status}}" 2>&1
Write-Output "  $psql"
Write-Output "  $redis"

Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Done."
Stop-Transcript
