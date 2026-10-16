@echo off
TITLE FOREXTELE 24/7 AUTONOMOUS LIVE TRADING ENGINE
COLOR 0A
chcp 65001 > nul
cd /d "%~dp0"

set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

echo ====================================================================
echo  FOREXTELE - 24/7 PERSISTENT AUTONOMOUS LIVE TRADING ENGINE
echo  1. Safely terminates stale Forex processes (NEVER touches SepPro)
echo  2. Connects to XM Global MT5 (Live Balance: $4,554.67 USD)
echo  3. BTCUSD Crypto Trading is LIVE RIGHT NOW (Sunday 24/7)
echo  4. Gold, Silver, and Forex Majors Auto-Wake at Sunday Market Open
echo  5. Survives VPS Reboots and Crashes with Windows Task Scheduler
echo ====================================================================
echo.

"%PYTHON_EXE%" -u launch_247_autonomous_live.py

echo.
echo ====================================================================
echo  Console view closed.
echo  NOTE: All trading engines CONTINUE RUNNING 24/7 in the background!
echo  To view the live monitor again, double-click this batch file.
echo ====================================================================
pause
