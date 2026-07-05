@echo off
title AutomateON Forex AI System Startup
echo =======================================================
echo    Starting AutomateON Forex System (MT5 ^& Telegram)
echo =======================================================
echo.

echo [1/3] Launching MT5 Live Order Executor (Dual Telegram Accounts)...
start "Forex Live Order Executor" cmd /k "py live_order_executor.py"

echo [2/3] Launching MT5 Strategy Execution Engine...
start "Forex Strategy Engine" cmd /k "py live_strategy_executor.py"

echo [3/3] Launching Flask UI Dashboard...
start "Forex Flask Dashboard" cmd /k "py dashboard_flask.py"

echo.
echo System is starting up in separate windows.
echo Dashboard will be available at http://127.0.0.1:5000
echo.
pause
