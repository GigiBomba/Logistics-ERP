@echo off
cd /d "%~dp0"
netstat -ano | findstr ":8000 " >nul 2>&1
if %errorlevel% equ 0 (
    echo Backend already running on port 8000.
) else (
    echo Starting Operion ERP Backend...
    start "Operion Backend" /MIN py -3.9 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
    timeout /t 3 /nobreak >nul
    echo Backend started.
)
pause
