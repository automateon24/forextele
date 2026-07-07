@echo off
title AutomateON Forex Master Engine
echo =======================================================
echo    Starting AutomateON Forex System (Master Runner)
echo =======================================================
echo.

:: Switch to the directory where the batch file is located
cd /d "%~dp0"

echo Launching all bots and dashboard in a single console...
py master_runner.py

pause
