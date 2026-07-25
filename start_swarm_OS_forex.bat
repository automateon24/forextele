@echo off
title FOREX SWARM OS - LIVE MASTER TERMINAL (EXCLUSIVE FOR FOREX)
color 0A

echo ==================================================================================
echo    INITIATING FOREX AI SWARM SYSTEM (MULTI-TIMEFRAME ENGINE & WEEKEND CRYPTO)      
echo ==================================================================================
echo.
echo [STEP 1] Pre-cleaning old Forex tasks and freeing Port 5555 & 8888...
call "%~dp0stop_swarm_OS_forex.bat" --auto
echo.
echo [STEP 2] Launching Interactive Real-Time Forex Console & Services...
echo (Dashboard UI will be warm and available on-demand at http://localhost:5555)
echo.
cd /d "C:\anlyzeforex\forextele"
py forex_live_terminal_monitor.py
pause
