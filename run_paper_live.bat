@echo off
echo ========================================================
echo Starting ForexTele Paper Trading Orchestrator (Live Log)
echo ========================================================
echo Press Ctrl+C to stop.
echo.

:: Ensure we are in the correct directory
cd /d "%~dp0"

:: Run the orchestrator
py scripts/run_production_orchestrator.py

echo.
echo Orchestrator stopped.
pause
