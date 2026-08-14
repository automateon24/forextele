@echo off
TITLE GOLD Part 1 Live 24/5 Production Engine
COLOR 0A
cls

echo ====================================================================
echo               GOLD PART 1 CORE 24/5 PRODUCTION ENGINE
echo ====================================================================
echo  Active Asset  : GOLD (XAUUSD) - Timeframe: M15
echo  Strategies    : GOLD_FVG_RETEST_M15, GOLD_SMC_CHOCH_M15
echo  Risk Caps     : Max 3 Open Positions, Max 2 on Gold, 0.02 Lots
echo  Execution     : Structure-based TP/SL, MT5 Broker Live Direct
echo  Session Filter: Hard-coded 18:00 - 22:59 UTC blocked
echo  Persistence   : Auto-Restart Loop Enabled (24/5 Non-Stop)
echo ====================================================================
echo.

cd /d "%~dp0"

if not exist "logs" mkdir logs

:RUN_LOOP
echo [%DATE% %TIME%] Starting Gold Part 1 Orchestrator Session... >> logs\gold_part1_supervisor.log
echo [%DATE% %TIME%] Orchestrator is ACTIVE. Watching MT5 market ticks...
echo.

:: Auto-detect virtual environment python executable
if exist "%~dp0..\.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%~dp0..\.venv\Scripts\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

"%PYTHON_CMD%" scripts\run_production_orchestrator.py

echo.
echo ====================================================================
echo [WARNING] Orchestrator exited or connection lost at %DATE% %TIME%.
echo Restarting in 5 seconds... (Press Ctrl+C to abort)
echo ====================================================================
echo [%DATE% %TIME%] Orchestrator EXITED. Auto-restarting in 5 seconds... >> logs\gold_part1_supervisor.log

timeout /t 5 /nobreak >nul
goto RUN_LOOP
