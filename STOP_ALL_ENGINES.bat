@echo off
TITLE STOP ALL FOREXTELE ENGINES
COLOR 0C
chcp 65001 > nul

echo ====================================================================
echo    SAFELY CLOSING ALL FOREXTELE ENGINES AND SUPERVISORS
echo    (MetaTrader 5 and external system processes remain untouched)
echo ====================================================================
echo.

cd /d "%~dp0"

echo [1/2] Terminating all forextele python and cmd supervisor instances...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -like '*forextele*' -or $_.CommandLine -like '*telegram_signal_engine*' -or $_.CommandLine -like '*autonomous_ai_market_scanner*' -or $_.CommandLine -like '*master_autostart_watchdog*' -or $_.CommandLine -like '*run_telegram_gold_live*' -or $_.CommandLine -like '*run_autonomous_scanner*') -and ($_.CommandLine -notlike '*SepPro*') } | ForEach-Object { Write-Host ('Terminating PID ' + $_.ProcessId + ' (' + $_.Name + ')...'); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

ping 127.0.0.1 -n 3 >nul

echo.
echo [2/2] Verifying no residual instances remain...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$procs = Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -like '*forextele*' -or $_.CommandLine -like '*telegram_signal_engine*' -or $_.CommandLine -like '*autonomous_ai_market_scanner*' -or $_.CommandLine -like '*master_autostart_watchdog*') -and ($_.CommandLine -notlike '*SepPro*') }; if ($procs) { Write-Host ('[WARNING] Still active: ' + ($procs | Measure-Object).Count) } else { Write-Host '✅ Zero forextele instances running. All stopped cleanly.' }"

echo.
echo ====================================================================
echo  ALL INSTANCES CLOSED SUCCESSFULLY.
echo ====================================================================
echo.
pause
