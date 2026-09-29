@echo off
TITLE FOREXTELE 3-DAY MULTI-ENGINE LIVE PERFORMANCE
COLOR 0B
chcp 65001 > nul
cd /d "%~dp0"

set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=py -3.11

"%PYTHON_EXE%" check_3day_performance.py

echo.
pause
