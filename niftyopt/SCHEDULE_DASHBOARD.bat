@echo off
:: ============================================================
::  UNIFIED DASHBOARD SCHEDULER
::  Creates/updates the Mon-Fri daily dashboard task at 9:18 AM
::  Run as Administrator to ensure permissions
:: ============================================================
chcp 65001 >nul
echo.
echo ============================================================
echo   SETTING UP UNIFIED TRADING DASHBOARD SCHEDULE
echo   Mon-Fri at 09:18 AM  |  Runs as SYSTEM in Background
echo ============================================================
echo.

set WORKDIR=C:\cursor\options\niftyopt

:: Delete task if it exists
schtasks /Delete /TN "NiftyOpt_Unified_Dashboard" /F >nul 2>&1

:: Create scheduled task (Runs START_UNIFIED_DASHBOARD.bat as SYSTEM hidden background task)
echo [CREATE] NiftyOpt_Unified_Dashboard  -  09:18 AM Mon-Fri
schtasks /Create /TN "NiftyOpt_Unified_Dashboard" /TR "\"%WORKDIR%\START_UNIFIED_DASHBOARD.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:18 /RL HIGHEST /RU SYSTEM /F

if %errorlevel%==0 (
    echo.
    echo   [OK] Task created successfully!
    echo   Dashboard will run silently in background at 9:18 AM Mon-Fri.
    echo   Access it anytime at http://localhost:8000
    echo.
) else (
    echo.
    echo   [ERROR] Failed to create scheduled task. 
    echo   Please right-click this batch file and select "Run as Administrator".
    echo.
)

:: Verify Task
echo Verifying task registration:
schtasks /Query /TN "NiftyOpt_Unified_Dashboard" /FO LIST /NH 2>nul | findstr "Task Name\|Next Run\|Status"
echo.
pause
