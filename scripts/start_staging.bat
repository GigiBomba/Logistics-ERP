@echo off
REM ────────────────────────────────────────────────────────────────────────
REM Operion ERP — Local staging harness launcher (see docs/staging-runbook.md)
REM
REM Usage:
REM   start_staging.bat            start uvicorn on port 8010 with staging env
REM   start_staging.bat -Docker    start via docker compose (compose.local.yaml)
REM
REM First run seeds data/staging.db with test users:
REM   driver@staging.local / dispatcher@staging.local  (password: staging-pass)
REM ────────────────────────────────────────────────────────────────────────
cd /d "%~dp0\.."

if /i "%~1"=="-Docker" goto :docker

REM ── Staging environment (override any value in .env.staging) ───────────
if exist .env.staging (
    for /f "usebackq tokens=1,* delims==" %%a in (".env.staging") do (
        if not "%%a"=="" if not "%%a:~0,1"=="#" set "%%a=%%b"
    )
)
set "OPERION_DB_ENGINE=sqlite"
set "OPERION_DB_PATH=data\staging.db"
set "OPERION_API_HOST=127.0.0.1"
set "OPERION_API_PORT=8010"
set "OPERION_API_WORKERS=1"
set "OPERION_ENV=development"
set "OPERION_API_BASE_URL=http://127.0.0.1:8010"
if not defined OPERION_JWT_SECRET_KEY set "OPERION_JWT_SECRET_KEY=staging-dev-only-secret-0000000000000000000000000000"
if not defined OPERION_API_KEY set "OPERION_API_KEY=staging-dev-only-api-key-0000000000000000000000000000"
if not defined OPERION_CORS_ORIGINS set "OPERION_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

REM ── Seed test users (idempotent) ───────────────────────────────────────
python scripts\seed_staging_users.py
if errorlevel 1 (
    echo Failed to seed staging DB.
    exit /b 1
)

echo Starting staging backend on http://127.0.0.1:8010 ...
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
exit /b %errorlevel%

:docker
echo Starting staging backend via Docker (compose.local.yaml) ...
docker compose -f compose.local.yaml up -d
exit /b %errorlevel%
