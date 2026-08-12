@echo off
TITLE ForexTele 24/7 Master Portfolio Live Execution Engine
COLOR 0A
CD /D "%~dp0"

echo ================================================================================
echo   STARTING FOREXTELE 24/7 MASTER PORTFOLIO LIVE EXECUTION ENGINE
echo   Targeting 100%%+ Monthly Profit across Gold & Silver Winning Strategies
echo   Press Ctrl+C to stop
echo ================================================================================
echo.

:: 1. Promote latest staging models to production
echo [INFO] Updating Production Model Registry...
C:\Python314\python.exe scripts/promote_model.py

echo.
echo [INFO] Launching 24/7/365 Non-Stop Master Execution Loop...
echo.

:LOOP
C:\Python314\python.exe scripts/run_master_portfolio_live.py
echo.
echo [WARNING] Live Orchestrator exited unexpectedly. Auto-restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto LOOP
