@echo off
TITLE STOP ALL FOREXTELE ENGINES
COLOR 0C
chcp 65001 > nul

echo ====================================================================
echo    SAFELY CLOSING ALL FOREXTELE ENGINES, SUPERVISORS AND TRADES
echo ====================================================================
echo.

cd /d "%~dp0"
set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe

echo [1/3] Closing any open MT5 positions and pending orders...
"%PYTHON_EXE%" scratch/kill_and_audit_all.py

echo.
echo [2/3] Force terminating all engine processes, supervisors, and batch runners...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -like '*breakout_boss*' -or $_.CommandLine -like '*run_breakout_boss*' -or $_.CommandLine -like '*autonomous_ai_market_scanner*' -or $_.CommandLine -like '*run_autonomous_scanner*' -or $_.CommandLine -like '*telegram_signal_engine*' -or $_.CommandLine -like '*run_telegram_gold_live*' -or $_.CommandLine -like '*ai_backtest_alignment_watchdog*' -or $_.CommandLine -like '*start_all_engines*' -or $_.CommandLine -like '*start_monday_live_engines*') -and ($_.CommandLine -notlike '*SepPro*') } | ForEach-Object { Write-Host ('Terminating PID ' + $_.ProcessId + ' (' + $_.Name + ')...'); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo [3/3] Final status check...
"%PYTHON_EXE%" scratch/kill_and_audit_all.py

echo.
echo ====================================================================
echo  ALL ENGINES STOPPED AND ALL POSITIONS CLOSED FOR THE WEEKEND!
echo ====================================================================
echo.
pause
