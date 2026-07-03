@echo off
REM ============================================================
REM  SETUP AUTO-START for MODULAR_TRADER_V3
REM  Registers TWO Windows Scheduled Tasks:
REM    1. Token refresh at 8:30 AM (already exists - verify)
REM    2. V3 Trader start at 9:15 AM (new)
REM  Run this ONCE as Administrator to set up for every day.
REM ============================================================

set PROJECT=c:\cursor\options\niftyopt
set PYTHON=%PROJECT%\venv\Scripts\python.exe
set V3_SCRIPT=%PROJECT%\MODULAR_TRADER_V3.py
set RUN_BAT=%PROJECT%\RUN_MODULAR_V3.bat

echo.
echo ================================================================
echo   SETTING UP AUTO-START FOR MODULAR TRADER V3
echo ================================================================
echo.

REM ── Task 1: Token refresh at 8:30 AM ─────────────────────────────
echo [1/2] Registering Token Refresh at 8:30 AM...
schtasks /create /tn "NiftyOpt_TokenRefresh" ^
    /tr "cmd /c \"%PROJECT%\DAILY_AUTO_LOGIN.bat\"" ^
    /sc daily /st 08:30 /f ^
    /ru "%USERNAME%" ^
    /rl highest ^
    /sd 01/01/2026
if %errorlevel%==0 (
    echo     OK - Token Refresh task registered.
) else (
    echo     Already exists or updated.
)

REM ── Task 2: V3 Trader at 9:15 AM (market open) ───────────────────
echo [2/2] Registering V3 Trader start at 9:15 AM...
schtasks /create /tn "NiftyOpt_V3_Trader" ^
    /tr "cmd /c \"%RUN_BAT%\" >> \"%PROJECT%\daily_data\scheduler_v3.log\" 2>&1" ^
    /sc daily /st 09:15 /f ^
    /ru "%USERNAME%" ^
    /rl highest ^
    /sd 01/01/2026
if %errorlevel%==0 (
    echo     OK - V3 Trader task registered for 9:15 AM daily.
) else (
    echo     Already exists or updated.
)

echo.
echo ================================================================
echo   VERIFICATION - Current Scheduled Tasks:
echo ================================================================
schtasks /query /tn "NiftyOpt_TokenRefresh" /fo LIST 2>nul | findstr "Task Name\|Next Run\|Status"
schtasks /query /tn "NiftyOpt_V3_Trader"    /fo LIST 2>nul | findstr "Task Name\|Next Run\|Status"

echo.
echo ================================================================
echo   SETUP COMPLETE
echo   Tomorrow morning:
echo     08:30 AM - Token auto-refreshed
echo     09:15 AM - V3 Trader auto-starts
echo.
echo   To remove auto-start:
echo     schtasks /delete /tn "NiftyOpt_V3_Trader" /f
echo ================================================================
echo.
pause
