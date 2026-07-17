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
taskkill /F /IM node.exe /T >nul 2>&1

:: Kill any process using port 5555 or 8888
echo [2/4] Releasing network ports...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8888" ^| find "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5555" ^| find "LISTENING"') do taskkill /f /pid %%a >nul 2>&1

:: Start Python Swarm Backend in its own persistent window
echo [3/4] Launching AI Swarm Backend (master_swarm_runner.py)...
start "SWARM BACKEND" cmd /k "cd /d C:\anlyzeforex\forextele && py master_swarm_runner.py"

:: Start React Frontend in its own persistent window  
echo [4/4] Launching React Dashboard (localhost:5555)...
start "SWARM DASHBOARD" cmd /k "cd /d C:\anlyzeforex\forextele\dashboard_ui && npm run dev -- --port 5555"

echo.
echo =============================================
echo  ALL SYSTEMS ONLINE
echo  Dashboard ^> open Chrome to: http://localhost:5555
echo  Backend  ^> WebSocket at:    ws://localhost:8888
echo =============================================
echo.
echo  Two windows launched. This launcher can be closed.
echo  The Swarm will keep running independently.
echo.
