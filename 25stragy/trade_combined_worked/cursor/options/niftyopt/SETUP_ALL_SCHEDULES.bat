@echo off
:: ============================================================
::  MASTER TRADING SCHEDULER SETUP
::  Creates/updates ALL Mon-Fri trading tasks
::  Run as Administrator
::  Next fire: Monday 2026-06-22
:: ============================================================
chcp 65001 >nul
echo.
echo ============================================================
echo   SETTING UP ALL TRADING ENGINE SCHEDULES
echo   Mon-Fri ONLY  ^|  Sat-Sun = NO TASKS
echo ============================================================
echo.

set WORKDIR=C:\cursor\options\niftyopt
if not exist "%WORKDIR%\logs" mkdir "%WORKDIR%\logs"

:: ---- HELPER: delete task if it exists ----
call :safe_delete "NiftyOpt_TokenRefresh"
call :safe_delete "NiftyOpt_V3_Trader"
call :safe_delete "NiftyOpt_V4_Trader"
call :safe_delete "NiftyOpt_V4_Adaptive"
call :safe_delete "NiftyOpt_Stragy_V15"
call :safe_delete "NiftyOpt_Unified_Dashboard"
call :safe_delete "NiftyOpt_EOD_Summary"

:: ---- DISABLE OLD TASKS ----
schtasks /Change /TN "DhanDailyTokenRefresh"    /Disable >nul 2>&1
schtasks /Change /TN "ModularTraderV3_Morning"  /Disable >nul 2>&1
schtasks /Change /TN "ModularTraderV3_Test"     /Disable >nul 2>&1
schtasks /Change /TN "V4_Paper_Trading"         /Disable >nul 2>&1
echo [DISABLED] Old/duplicate tasks disabled.
echo.

:: ===========================================================
:: 1. TOKEN REFRESH — 08:30 AM Mon-Fri
:: ===========================================================
echo [CREATE] NiftyOpt_TokenRefresh  -  08:30 AM Mon-Fri
schtasks /Create /TN "NiftyOpt_TokenRefresh" /TR "\"%WORKDIR%\DAILY_AUTO_LOGIN.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 08:30 /RL HIGHEST /RU SYSTEM /F
if %errorlevel%==0 (echo   [OK]) else (echo   [WARN] Check permissions)

:: ===========================================================
:: [DISABLED] V3 TRADER, V4 TRADER, V4 ADAPTIVE
:: These have been fully absorbed into Stragy V15
:: ===========================================================

:: ===========================================================
:: 5. STRAGY V15 (NEW) — 09:20 AM Mon-Fri
:: ===========================================================
echo [CREATE] NiftyOpt_Stragy_V15    -  09:20 AM Mon-Fri
schtasks /Create /TN "NiftyOpt_Stragy_V15" /TR "cmd /c start \"Stragy V15\" \"%WORKDIR%\RUN_STRAGY_V15.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:20 /RL HIGHEST /RU SYSTEM /F
if %errorlevel%==0 (echo   [OK]) else (echo   [WARN] Check permissions)

:: ===========================================================
:: 5b. UNIFIED DASHBOARD — 09:18 AM Mon-Fri
:: ===========================================================
echo [CREATE] NiftyOpt_Unified_Dashboard -  09:18 AM Mon-Fri
schtasks /Create /TN "NiftyOpt_Unified_Dashboard" /TR "\"%WORKDIR%\START_UNIFIED_DASHBOARD.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:18 /RL HIGHEST /RU SYSTEM /F
if %errorlevel%==0 (echo   [OK]) else (echo   [WARN] Check permissions)

:: ===========================================================
:: 6. EOD SUMMARY — 15:30 PM Mon-Fri
:: ===========================================================
echo [CREATE] NiftyOpt_EOD_Summary   -  15:30 PM Mon-Fri
schtasks /Create /TN "NiftyOpt_EOD_Summary" /TR "cmd /c \"%WORKDIR%\EOD_SUMMARY.bat\" >> \"%WORKDIR%\logs\eod.log\" 2>&1" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:30 /RL HIGHEST /RU SYSTEM /F
if %errorlevel%==0 (echo   [OK]) else (echo   [WARN] Check permissions)

echo.
echo ============================================================
echo   FINAL SCHEDULE - ALL TASKS (MON-FRI ONLY)
echo ============================================================
echo.
echo   Time     Task Name                  Engine / Description
echo   -------- -------------------------- ----------------------------------------
echo   08:30 AM NiftyOpt_TokenRefresh      Dhan API token refresh (prerequisite)
echo   09:18 AM NiftyOpt_Unified_Dashboard Unified Trading Dashboard Web Server
echo   09:20 AM NiftyOpt_Stragy_V15        STRAGY V15 - 36 strats x 4 indices (NEW)
echo   15:30 PM NiftyOpt_EOD_Summary       End-of-Day PnL report + token check
echo.
echo   [DISABLED] V3_Trader, V4_Trader, V4_Adaptive (absorbed by V15)
echo   [DISABLED] ModularTraderV3_Morning  (replaced by V15)
echo   [DISABLED] V4_Paper_Trading         (replaced by V15)
echo.
echo ============================================================
echo   SATURDAY ^& SUNDAY: NO TASKS WILL RUN
echo   System runs FOREVER every weekday until you stop it.
echo   To stop all: Run STOP_ALL_TRADING.bat
echo ============================================================
echo.

:: ---- VERIFY ----
echo Verifying scheduled tasks...
echo.
schtasks /Query /TN "NiftyOpt_TokenRefresh"  /FO LIST /NH 2>nul | findstr "Task Name\|Next Run\|Status"
schtasks /Query /TN "NiftyOpt_V3_Trader"     /FO LIST /NH 2>nul | findstr "Task Name\|Next Run\|Status"
schtasks /Query /TN "NiftyOpt_V4_Trader"     /FO LIST /NH 2>nul | findstr "Task Name\|Next Run\|Status"
schtasks /Query /TN "NiftyOpt_V4_Adaptive"   /FO LIST /NH 2>nul | findstr "Task Name\|Next Run\|Status"
schtasks /Query /TN "NiftyOpt_Unified_Dashboard" /FO LIST /NH 2>nul | findstr "Task Name\|Next Run\|Status"
schtasks /Query /TN "NiftyOpt_Stragy_V15"    /FO LIST /NH 2>nul | findstr "Task Name\|Next Run\|Status"
schtasks /Query /TN "NiftyOpt_EOD_Summary"   /FO LIST /NH 2>nul | findstr "Task Name\|Next Run\|Status"

echo.
echo Setup complete! Press any key to close.
pause >nul
goto :eof

:safe_delete
schtasks /Delete /TN "%~1" /F >nul 2>&1
goto :eof
