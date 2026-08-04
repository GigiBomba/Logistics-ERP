<#
.SYNOPSIS
    Start the LOCAL staging backend harness for the Operion ERP backend.

.DESCRIPTION
    Starts the FastAPI backend in "staging-like" mode against a dedicated
    file-based SQLite database (data/staging.db), without requiring Docker:

      1. Copies .env.staging.example -> .env.staging when .env.staging is missing.
      2. Loads every key from .env.staging as a REAL process environment
         variable so the repo-root .env (always loaded by backend/main.py via
         python-dotenv, override=False) can never shadow the staging values.
      3. Ensures the DB schema and seeds the staging smoke users
         (python -m scripts.staging_seed).
      4. Starts uvicorn on the staging host/port (default 127.0.0.1:8900),
         detached, logging to data/logs/staging-uvicorn.{out,err}.log.

    With the -Docker switch (requires a working Docker daemon) the repo's
    existing compose.local.yaml stack is used instead (port 8000):
      - `docker compose -f compose.local.yaml up -d`
      - seeds the container's DB (data/cashflow.db) with the staging users
      - exports the API key from the repo-root .env as STAGING_API_KEY so the
        smoke test can authenticate against the container.

.EXAMPLE
    scripts\start_staging.ps1
    scripts\start_staging.ps1 -Docker
    scripts\start_staging.ps1 -Stop
    scripts\start_staging.ps1 -Status

.NOTES
    PowerShell 5.1.  ASCII-only source (no BOM).  The bat wrapper
    scripts\start_staging.bat calls this.
#>
[CmdletBinding()]
param(
    [switch]$Docker,
    [switch]$Stop,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $RepoRoot

$envFile = Join-Path $RepoRoot ".env.staging"
$envExample = Join-Path $RepoRoot ".env.staging.example"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Staging($msg) {
    Write-Host "[staging] $msg"
}

function Set-EnvFromFile($path) {
    # Applies every KEY=VALUE from a simple env file to the CURRENT process
    # environment (empty values included), so children inherit them and the
    # repo-root .env cannot override them (python-dotenv override=False).
    Get-Content -LiteralPath $path | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            $key = $line.Substring(0, $idx).Trim()
            $value = $line.Substring($idx + 1).Trim()
            if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            # SetEnvironmentVariable keeps empty values (unlike $env:X = "").
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

function Test-PortListening([int]$port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return [bool]$conn
}

function Wait-ForHealth([string]$url, [int]$maxSeconds = 45) {
    for ($i = 0; $i -lt $maxSeconds; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "$url/api/v1/health/live" -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { return $true }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

# ---------------------------------------------------------------------------
# .env.staging bootstrap
# ---------------------------------------------------------------------------
if (-not (Test-Path -LiteralPath $envFile)) {
    if (Test-Path -LiteralPath $envExample) {
        Copy-Item -LiteralPath $envExample -Destination $envFile
        Write-Staging ".env.staging created from .env.staging.example (edit it to taste)."
    } else {
        Write-Staging "ERROR: neither .env.staging nor .env.staging.example exists."
        exit 1
    }
}

Set-EnvFromFile $envFile

$hostname = if ($env:OPERION_API_HOST) { $env:OPERION_API_HOST } else { "127.0.0.1" }
$portText = if ($env:OPERION_API_PORT) { $env:OPERION_API_PORT } else { "8900" }
$port = 8900
[void][int]::TryParse($portText, [ref]$port)
if ($port -eq 0) { $port = 8900 }

# ---------------------------------------------------------------------------
# Stop / Status
# ---------------------------------------------------------------------------
if ($Stop) {
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -match "uvicorn backend.main:app" -and $_.CommandLine -match "--port $port" }
    foreach ($p in $procs) {
        Write-Staging "Stopping uvicorn PID $($p.ProcessId) on port $port"
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    exit 0
}

if ($Status) {
    $listening = Test-PortListening $port
    $base = "http://127.0.0.1:$port"
    $healthy = if (Wait-ForHealth $base 3) { "yes" } else { "no" }
    Write-Staging "Staging port : $port (listening=$listening)"
    Write-Staging "Health (/api/v1/health/live) : $healthy"
    exit 0
}

# ---------------------------------------------------------------------------
# Docker mode - repo's existing compose.local.yaml stack
# ---------------------------------------------------------------------------
if ($Docker) {
    docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Staging "ERROR: -Docker requested but `docker info` failed - Docker is not available."
        exit 1
    }
    Write-Staging "Docker available - starting via compose.local.yaml (port 8000)..."
    docker compose -f compose.local.yaml up -d
    if ($LASTEXITCODE -ne 0) { Write-Staging "ERROR: docker compose up failed."; exit 1 }

    # The container reads the repo-root .env and defaults to data/cashflow.db.
    # Seed the staging users there (idempotent, additive) so login works.
    Write-Staging "Seeding staging users into the container DB (data/cashflow.db)..."
    python -m scripts.staging_seed --db "data/cashflow.db"
    if ($LASTEXITCODE -ne 0) { Write-Staging "ERROR: staging seed failed."; exit 1 }

    # Export the container's API key so the smoke test can authenticate.
    $rootEnvPath = Join-Path $RepoRoot ".env"
    if (Test-Path -LiteralPath $rootEnvPath) {
        $rootEnv = @{}
        Get-Content -LiteralPath $rootEnvPath | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                $idx = $line.IndexOf("=")
                $rootEnv[$line.Substring(0, $idx).Trim()] = $line.Substring($idx + 1).Trim()
            }
        }
        if ($rootEnv.ContainsKey("OPERION_API_KEY") -and $rootEnv["OPERION_API_KEY"]) {
            [System.Environment]::SetEnvironmentVariable("STAGING_API_KEY", $rootEnv["OPERION_API_KEY"], "Process")
            Write-Staging "STAGING_API_KEY exported from repo-root .env."
        }
    }
    [System.Environment]::SetEnvironmentVariable("STAGING_BASE_URL", "http://127.0.0.1:8000", "Process")

    Write-Staging "Waiting for the container API on port 8000..."
    if (Wait-ForHealth "http://127.0.0.1:8000") {
        Write-Staging "Container API is healthy at http://127.0.0.1:8000"
    } else {
        Write-Staging "WARNING: API did not become healthy in time - check: manage.bat logs"
    }
    Write-Staging "Smoke test:  pytest tests/staging/test_staging_smoke.py -v"
    Write-Staging "Stop:         manage.bat down  (or: start_staging.ps1 -Docker -Stop)"
    exit 0
}

# ---------------------------------------------------------------------------
# Plain uvicorn mode (default - works without Docker)
# ---------------------------------------------------------------------------
Write-Staging "Ensuring DB schema + seeding staging users..."
python -m scripts.staging_seed --env-file $envFile
if ($LASTEXITCODE -ne 0) { Write-Staging "ERROR: staging seed failed."; exit 1 }

$base = "http://127.0.0.1:$port"
$alreadyUp = Wait-ForHealth $base 2
if ($alreadyUp) {
    Write-Staging "A staging server is already responding at $base - nothing to start."
} else {
    $logDir = Join-Path $RepoRoot "data\logs"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $outLog = Join-Path $logDir "staging-uvicorn.out.log"
    $errLog = Join-Path $logDir "staging-uvicorn.err.log"

    Write-Staging "Starting uvicorn on http://$hostname`:$port (detached)..."
    $proc = Start-Process -FilePath "python" `
        -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", $hostname, "--port", "$port") `
        -WorkingDirectory $RepoRoot `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog

    Write-Staging "uvicorn PID $($proc.Id) - logs in data/logs/staging-uvicorn.*.log"
    Write-Staging "Waiting for health at $base/api/v1/health/live ..."
    if (Wait-ForHealth $base) {
        Write-Staging "Staging harness is UP at $base"
    } else {
        Write-Staging "WARNING: server did not answer health within 45s."
        Write-Staging "Check data/logs/staging-uvicorn.err.log for startup errors."
    }
}

Write-Staging ""
Write-Staging "Base URL      : $base  (mobile Android emulator: http://10.0.2.2:$port)"
Write-Staging "Swagger docs  : $base/docs"
Write-Staging "DB            : $env:OPERION_DB_PATH"
Write-Staging "Smoke test    : pytest tests/staging/test_staging_smoke.py -v"
Write-Staging "Stop server   : scripts\start_staging.ps1 -Stop"
Write-Staging ""
