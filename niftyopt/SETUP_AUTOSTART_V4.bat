@echo off
REM ============================================================
REM  SETUP AUTO-START for MODULAR_TRADER_V4 and ADAPTIVE_V4
REM  Registers THREE Windows Scheduled Tasks:
REM    1. Token refresh at 8:30 AM (shared with V3)
REM    2. V4 Trader start at 9:15 AM
REM    3. V4 Adaptive start at 9:17 AM (2 min after V4)
REM  Run this ONCE as Administrator to set up for every day.
REM ============================================================

set PROJECT=c:\cursor\options\niftyopt
set PYTHON=%PROJECT%\venv\Scripts\python.exe
set V4_SCRIPT=%PROJECT%\MODULAR_TRADER_V4.py
set ADAPTIVE_SCRIPT=%PROJECT%\ADAPTIVE_V4.py
set RUN_V4_BAT=%PROJECT%\RUN_MODULAR_V4.bat
set RUN_ADAPTIVE_BAT=%PROJECT%\START_ADAPTIVE_V4.bat
set SCHED_V4_BAT=%PROJECT%\SCHED_TRADER_V4.bat
set SCHED_ADAPTIVE_BAT=%PROJECT%\SCHED_ADAPTIVE_V4.bat

echo.
echo ================================================================
echo   SETTING UP AUTO-START FOR V4 TRADER + ADAPTIVE ENGINE
echo ================================================================
echo.

REM ── Task 1: Token refresh at 8:30 AM (shared with V3) ─────────────
echo [1/4] Registering Token Refresh at 8:30 AM... (shared with V3)
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

REM ── Task 2: V4 Trader at 9:15 AM ─────────────────────────────────
echo [2/4] Registering V4 Trader start at 9:15 AM...
schtasks /create /tn "NiftyOpt_V4_Trader" ^
    /tr "cmd /c \"%SCHED_V4_BAT%\" >> \"%PROJECT%\daily_data\scheduler_v4.log\" 2>&1" ^
    /sc daily /st 09:15 /f ^
    /ru "%USERNAME%" ^
    /rl highest ^
    /sd 01/01/2026
if %errorlevel%==0 (
    echo     OK - V4 Trader task registered for 9:15 AM daily.
) else (
    echo     Already exists or updated.
)

REM ── Task 3: V4 Adaptive at 9:17 AM (2 min after V4) ──────────────
echo [3/4] Registering V4 Adaptive start at 9:17 AM...
schtasks /create /tn "NiftyOpt_V4_Adaptive" ^
    /tr "cmd /c \"%SCHED_ADAPTIVE_BAT%\" >> \"%PROJECT%\daily_data\scheduler_adaptive.log\" 2>&1" ^
    /sc daily /st 09:17 /f ^
    /ru "%USERNAME%" ^
    /rl highest ^
    /sd 01/01/2026
if %errorlevel%==0 (
    echo     OK - V4 Adaptive task registered for 9:17 AM daily.
) else (
    echo     Already exists or updated.
)

REM ── Task 4: EOD Summary at 3:30 PM ───────────────────────────────
echo [4/4] Registering EOD Summary at 3:30 PM...
schtasks /create /tn "NiftyOpt_EOD_Summary" ^
    /tr "cmd /c \"%PROJECT%\EOD_SUMMARY.bat\" >> \"%PROJECT%\daily_data\eod.log\" 2>&1" ^
    /sc daily /st 15:30 /f ^
    /ru "%USERNAME%" ^
    /rl highest ^
    /sd 01/01/2026
if %errorlevel%==0 (
    echo     OK - EOD Summary task registered for 3:30 PM daily.
) else (
    echo     Already exists or updated.
)

echo.
echo ================================================================
echo   VERIFICATION - Current Scheduled Tasks:
echo ================================================================
echo.
schtasks /query /tn "NiftyOpt_TokenRefresh" /fo LIST 2>nul | findstr "Task Name\|Next Run\|Status" 
schtasks /query /tn "NiftyOpt_V4_Trader"    /fo LIST 2>nul | findstr "Task Name\|Next Run\|Status"
schtasks /query /tn "NiftyOpt_V4_Adaptive"   /fo LIST 2>nul | findstr "Task Name\|Next Run\|Status"
schtasks /query /tn "NiftyOpt_EOD_Summary"   /fo LIST 2>nul | findstr "Task Name\|Next Run\|Status"

echo.
echo ================================================================
echo   SETUP COMPLETE
echo   Tomorrow morning (June 5, 2026):
echo     08:30 AM - Token auto-refreshed
echo     09:15 AM - V4 Trader auto-starts
echo     09:17 AM - V4 Adaptive auto-starts (2 min after V4)
echo     15:30 PM - EOD Summary auto-runs
echo.
echo   To remove auto-start:
echo     schtasks /delete /tn "NiftyOpt_V4_Trader" /f
echo     schtasks /delete /tn "NiftyOpt_V4_Adaptive" /f
echo     schtasks /delete /tn "NiftyOpt_EOD_Summary" /f
echo ================================================================
echo.
pause
