@echo off
cd /d "%~dp0"

if "%1"=="" goto :usage

if /i "%1"=="up" goto :up
if /i "%1"=="down" goto :down
if /i "%1"=="restart" goto :restart
if /i "%1"=="rebuild" goto :rebuild
if /i "%1"=="logs" goto :logs
if /i "%1"=="status" goto :status

echo Unknown command: %1
goto :usage

:up
echo Starting backend...
docker compose -f compose.local.yaml up -d
if %errorlevel% equ 0 (
    echo Backend started.
) else (
    echo Failed to start. Try: %0 rebuild
)
goto :eof

:down
echo Stopping backend...
docker compose -f compose.local.yaml down
echo Backend stopped.
goto :eof

:restart
echo Restarting backend...
docker compose -f compose.local.yaml down
docker compose -f compose.local.yaml up -d
echo Backend restarted.
goto :eof

:rebuild
echo Rebuilding and starting backend...
docker compose -f compose.local.yaml up -d --build
if %errorlevel% equ 0 (
    echo Backend rebuilt and started.
) else (
    echo Build failed. Check the output above.
)
goto :eof

:logs
docker compose -f compose.local.yaml logs -f
goto :eof

:status
echo === Container ===
docker ps --filter "name=calculatorlogistica-api" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
echo === Port 8000 ===
netstat -ano | findstr ":8000 " | findstr "LISTENING"
goto :eof

:usage
echo Usage: manage.bat COMMAND
echo.
echo Commands:
echo   up        Start the backend container
echo   down      Stop the backend container
echo   restart   Restart the backend container
echo   rebuild   Rebuild image and start (use after code changes)
echo   logs      Tail container logs (Ctrl+C to exit)
echo   status    Show container status and port check
echo.
goto :eof
