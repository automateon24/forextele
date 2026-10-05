@echo off
TITLE FOREXTELE 24/7 AUTONOMOUS SUITE - RESTART & LIVE MONITOR
COLOR 0E
chcp 65001 > nul
cd /d "%~dp0"

set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

echo ====================================================================
echo  RESTARTING FOREXTELE SUITE: FRESH CLEAN START & 24/7 PERSISTENCE
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
