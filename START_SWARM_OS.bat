@echo off
title FOREX SWARM OS - LAUNCHER
color 0A

echo =============================================
echo    FOREX AI SWARM OS - AUTONOMOUS LAUNCH
echo =============================================
echo.

:: Kill any existing instances cleanly
echo [1/4] Clearing old processes...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM py.exe /T >nul 2>&1
timeout /t 3 /nobreak >nul

:: Kill any process using port 5555 or 8888
echo [2/4] Releasing network ports...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5555 :8888" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 2 /nobreak >nul

:: Start Python Swarm Backend in its own persistent window
echo [3/4] Launching AI Swarm Backend (master_swarm_runner.py)...
start "SWARM BACKEND" /D "C:\anlyzeforex\forextele" cmd /k "py master_swarm_runner.py"
timeout /t 5 /nobreak >nul

:: Start React Frontend in its own persistent window
echo [4/4] Launching React Dashboard (localhost:5555)...
start "SWARM DASHBOARD" /D "C:\anlyzeforex\forextele\dashboard_ui" cmd /k "npm run dev -- --port 5555"
timeout /t 5 /nobreak >nul

echo.
echo =============================================
echo  ALL SYSTEMS ONLINE
echo  Dashboard: http://localhost:5555
echo  Backend:   ws://localhost:8888
echo =============================================
echo.
echo  Both windows are running independently.
echo  Close this launcher - systems stay alive.
echo.
pause
