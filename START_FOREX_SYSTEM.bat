@echo off
title AutomateON Forex AI System Startup
echo =======================================================
echo    Starting AutomateON Forex System (MT5 & Telegram)
echo =======================================================
echo.

echo [1/2] Launching MT5 Live Order Executor (Dual Telegram Accounts)...
start "Forex Live Order Executor" cmd /c "python live_order_executor.py"

echo [2/2] Launching Flask UI Dashboard...
start "Forex Flask Dashboard" cmd /c "python dashboard_flask.py"

echo.
echo System is starting up in separate windows.
echo Dashboard will be available at http://127.0.0.1:5000
echo.
pause
