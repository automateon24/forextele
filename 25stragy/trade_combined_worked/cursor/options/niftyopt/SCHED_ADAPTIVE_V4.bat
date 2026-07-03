@echo off
title NIFTY ADAPTIVE ENGINE V4
color 0B
:: Scheduler-safe wrapper for ADAPTIVE ENGINE V4

cd /d "c:\cursor\options\niftyopt"

:: Create dirs if needed
if not exist "daily_data" mkdir daily_data
if not exist "adaptive_data" mkdir adaptive_data

:: Use own log file (not shared - avoids file lock)
for /f %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set dt=%%a
set MYLOG=daily_data\adaptive_v4_%dt%.log

echo ================================================================
echo  NIFTY ADAPTIVE ENGINE V4 - Starting up...
echo  Log: %MYLOG%
echo ================================================================
echo.

:: Activate venv
call .\venv\Scripts\activate.bat

echo [OK] Starting Adaptive Engine...
echo.

:: Run Adaptive Engine - output to screen AND log file
.\venv\Scripts\python.exe ADAPTIVE_V4.py 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%MYLOG%' -Append"

call .\venv\Scripts\deactivate.bat

echo.
echo ================================================================
echo  ADAPTIVE ENGINE V4 - END OF DAY SUMMARY
echo  Date: %date%  Time: %time%
echo ================================================================
echo.

:: Show today's adaptive corrections and learnings
echo --- ADAPTIVE LEARNINGS TODAY ---
powershell -NoProfile -Command "Get-Content '%MYLOG%' | Where-Object {$_ -match 'CORRECT|LEARN|ADAPT|WROTE|CONFIG|EOD|pattern'} | Select-Object -Last 20 | ForEach-Object { Write-Host $_ }"

echo.
echo ================================================================
echo  Full log: %MYLOG%
echo ================================================================
echo.
echo  Press any key to close this window...
pause >nul
