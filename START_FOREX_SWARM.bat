@echo off
title FOREX AI SWARM OS
echo =======================================================
echo    Booting Forex Multi-Agent Swarm OS
echo =======================================================
echo.

:: Switch to the directory where the batch file is located
cd /d "%~dp0"

echo [1/3] Starting React Glassmorphism Dashboard...
start "React UI" cmd /c "cd dashboard_ui && npm run dev"

echo [2/3] Starting Swarm Master Node...
py master_swarm_runner.py

pause
