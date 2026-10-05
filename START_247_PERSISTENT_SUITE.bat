@echo off
TITLE FOREXTELE 24/7 AUTONOMOUS SUITE - CONSOLIDATED LIVE MONITOR
COLOR 0A
chcp 65001 > nul
cd /d "%~dp0"

set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

echo ====================================================================
echo  FOREXTELE - 24/7 PERSISTENT 1-MONTH AUTONOMOUS TRADING SUITE
echo  [1] BreakoutBoss v2 (5 Compounding Models + Gann on Gold M5)
echo  [2] Autonomous SMC AI (Institutional M15 FVG & Liquidity Sweeps)
echo  [3] Telegram VIP Engine (40+ Channels + AI Swarm Conviction Filter)
echo  [4] 24/7 Master Watchdog (Survives Reboots & Self-Heals Drops)
echo  [5] Daily AI Trade Learning & Continuous Auto-Optimization
echo ====================================================================
echo.

"%PYTHON_EXE%" -u consolidated_live_suite.py

echo.
echo ====================================================================
echo  Live monitor window closed.
echo  NOTE: All 3 Engines and Master Watchdog CONTINUE RUNNING 24/7
echo  in the background for 1 month without interruption!
echo  To view live monitor again, run START_247_PERSISTENT_SUITE.bat
echo ====================================================================
pause
