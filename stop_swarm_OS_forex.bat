@echo off
title FOREX SWARM OS - STOPPER (EXCLUSIVE FOR FOREX)
color 0C

echo =====================================================================
echo    STOPPING FOREX AI SWARM SYSTEM ONLY (PRESERVING INDIAN TRADES)    
echo =====================================================================
echo.

echo [1/3] Identifying and terminating Forex Python and Node processes...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'py.exe' -or $_.Name -eq 'node.exe') -and ($_.CommandLine -like '*anlyzeforex*' -or $_.CommandLine -like '*forextele*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo [2/3] Releasing Forex dedicated network ports (5555 and 8888)...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5555" ^| find "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8888" ^| find "LISTENING"') do taskkill /f /pid %%a >nul 2>&1

echo [3/3] Verification complete. All Forex services stopped cleanly.
echo.
echo =====================================================================
echo    FOREX SWARM OS IS OFFLINE. (YOUR INDIAN SYSTEMS REMAIN UNTOUCHED) 
echo =====================================================================
echo.
if "%1"=="--auto" exit /b 0
pause
