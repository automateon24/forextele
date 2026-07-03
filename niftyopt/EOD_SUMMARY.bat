@echo off
title EOD DAILY SUMMARY
color 0E
cd /d "C:\cursor\options\niftyopt"

for /f %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set DT=%%a
for /f %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%a

echo.
echo ================================================================================
echo   NIFTY OPTIONS TRADER - END OF DAY SUMMARY
echo   Date: %TODAY%
echo ================================================================================

REM ── Run Python analysis script ─────────────────────────────────────────────
.\venv\Scripts\python.exe "%~dp0EOD_ANALYSIS.py" %DT%

echo.
echo ================================================================================
echo   TOKEN STATUS
echo ================================================================================
.\venv\Scripts\python.exe EOD_TOKEN_CHECK.py

echo.
echo ================================================================================
echo   ADAPTIVE ENGINE - WHAT IT LEARNED TODAY
echo ================================================================================
powershell -NoProfile -Command "$f='daily_data\adaptive_v4_%DT%.log'; if(Test-Path $f){Get-Content $f | Where-Object{$_ -match 'CORRECT|LEARN|ADAPT|WROTE|Regime|correction|pattern|param'} | Select-Object -Last 15 | ForEach-Object{Write-Host '  ' $_}}else{Write-Host '  No adaptive log found for today'}"

echo.
echo ================================================================================
echo   SCHEDULER LOG - TOKEN REFRESH TODAY
echo ================================================================================
powershell -NoProfile -Command "Get-Content 'logs\scheduler.log' | Where-Object{$_ -match '%TODAY%' -and $_ -match 'SUCCESS|FAIL|ERROR|Token'} | ForEach-Object{Write-Host '  ' $_}"

echo.
echo ================================================================================
echo   FILES FOR TOMORROW'S PROGRAMS
echo   Copy these values into your next strategy/backtest
echo ================================================================================
echo   Trades CSV  : daily_data\modular_trades_%DT%.csv
echo   V3 CSV      : daily_data\v3_trades_%DT%.csv
echo   Decisions   : daily_data\decisions_%DT%.log
echo   V5 Full Log : daily_data\trader_v5_%DT%.log
echo   Adaptive    : daily_data\adaptive_v4_%DT%.log
echo ================================================================================
echo.
echo   Press any key to close...
pause >nul
