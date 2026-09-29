@echo off
TITLE BREAKOUTBOSS - AUTONOMOUS GOLD BREAKOUT ENGINE
COLOR 0B
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"

echo ====================================================================
echo    BREAKOUTBOSS - 24/7 AUTONOMOUS MULTI-SESSION GOLD ENGINE
echo ====================================================================
echo.

set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=py -3.11

:loop
echo [%date% %time%] Starting BreakoutBoss Engine...
"%PYTHON_EXE%" -u breakout_boss_engine.py
echo.
echo [%date% %time%] BreakoutBoss stopped or crashed. Restarting in 5s...
ping 127.0.0.1 -n 6 >nul
goto loop
