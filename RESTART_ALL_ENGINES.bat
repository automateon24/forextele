@echo off
TITLE RESTART ALL FOREXTELE ENGINES
COLOR 0E
chcp 65001 > nul

cd /d "%~dp0"

echo ====================================================================
echo    RESTARTING ALL FOREXTELE AUTONOMOUS ENGINES WITH ALL FIXES
echo ====================================================================
echo.

echo [PHASE 1] Terminating all old running instances and cmd wrappers...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -like '*telegram_signal_engine*' -or $_.CommandLine -like '*autonomous_ai_market_scanner*' -or $_.CommandLine -like '*breakout_boss*' -or $_.CommandLine -like '*run_breakout_boss*' -or $_.CommandLine -like '*master_autostart_watchdog*' -or $_.CommandLine -like '*run_telegram_gold_live*' -or $_.CommandLine -like '*run_autonomous_scanner*') -and ($_.CommandLine -notlike '*SepPro*') -and ($_.CommandLine -notlike '*RESTART_ALL_ENGINES*') } | ForEach-Object { Write-Host ('Closing PID ' + $_.ProcessId + ' (' + $_.Name + ')...'); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo Waiting 3 seconds for port and socket release...
ping 127.0.0.1 -n 4 >nul

echo.
echo [PHASE 2] Starting fresh instances with all AI and Trend fixes applied...
call START_ALL_ENGINES.bat
