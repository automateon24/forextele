@echo off
title NIFTY V4 TRADER
color 0A
:: Scheduler-safe wrapper for MODULAR TRADER V4

cd /d "c:\cursor\options\niftyopt"

:: Create daily_data dir if needed
if not exist "daily_data" mkdir daily_data

:: Use own log file (not shared - avoids file lock)
for /f %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set dt=%%a
set MYLOG=daily_data\trader_v4_%dt%.log

echo ================================================================
echo  NIFTY MODULAR TRADER V4 - Starting up...
echo  Log: %MYLOG%
echo ================================================================
echo.

:: Activate venv
call .\venv\Scripts\activate.bat

:: Check token file
if not exist "config\dhan_tokens.json" (
    echo [ERROR] config\dhan_tokens.json not found!
    echo Please run the token refresh first.
    pause
    exit /b 1
)
echo [PREFLIGHT] Token file found.

:: Run pre-flight tests before trading
echo [PREFLIGHT] Running V4 test suite...
.\venv\Scripts\python.exe tests\test_modular_trader_v4.py > daily_data\preflight_%dt%.txt 2>&1
if errorlevel 1 (
    echo [PREFLIGHT] TESTS FAILED - Not starting trader!
    echo [PREFLIGHT] Review: daily_data\preflight_%dt%.txt
    pause
    exit /b 1
)
echo [PREFLIGHT] All tests passed. Starting V4 engine...
echo.

:: Run V4 - output to screen AND log file
.\venv\Scripts\python.exe MODULAR_TRADER_V4.py 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%MYLOG%' -Append"

call .\venv\Scripts\deactivate.bat

echo.
echo ================================================================
echo  NIFTY V4 TRADER - END OF DAY SUMMARY
echo  Date: %date%  Time: %time%
echo ================================================================
echo.

:: Extract today's P&L summary from log
echo --- TRADES TODAY ---
findstr /i "TOTAL NET P&L\|NET P&L\|Trades:\|EOD\|CLOSED\|profit\|loss" "%MYLOG%" 2>nul | findstr /v "WAITING\|HEALTH" | tail -20 2>nul
powershell -NoProfile -Command "Get-Content '%MYLOG%' | Where-Object {$_ -match 'TOTAL NET|NET P.L|EOD|CLOSED|profit|loss' -and $_ -notmatch 'WAITING|HEALTH'} | Select-Object -Last 15 | ForEach-Object { Write-Host $_ }"

echo.
echo ================================================================
echo  Full log: %MYLOG%
echo ================================================================
echo.
echo  Press any key to close this window...
pause >nul
