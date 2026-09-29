@echo off
TITLE FOREXTELE MASTER 24/7 AUTOSTART WATCHDOG
COLOR 0A
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"

set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=py -3.11

"%PYTHON_EXE%" master_autostart_watchdog.py
