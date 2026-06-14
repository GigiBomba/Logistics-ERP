@echo off
REM Install Windows Task Scheduler entry for Operion ERP Alert Checker
REM Run as Administrator to install the scheduled task.

set "SCRIPT_DIR=%~dp0"
set "PYTHON_CMD=python"

echo Installing Operion ERP Alert Checker scheduled task...
echo.

REM Create the task that runs every 15 minutes
schtasks /Create /SC MINUTE /MO 15 /TN "Operion ERP Alert Checker" /TR "'%PYTHON_CMD%' -m scripts.alert_checker" /F /IT /RL HIGHEST

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Task installed successfully!
    echo The alert checker will run every 15 minutes.
    echo To verify, run: schtasks /Query /TN "Operion ERP Alert Checker"
) else (
    echo.
    echo Failed to install task. Try running this script as Administrator.
    echo Right-click the file and select "Run as administrator".
)

pause
