@echo off
title Telegram Live Engine
echo ================================================================
echo  Telegram Live Signal Engine
echo ================================================================
echo  Starting telegram_signal_engine.py with UTF-8 encoding...
echo.

cd /d "C:\25stragy"
set PYTHONIOENCODING=utf-8
set PYTHON=C:\cursor\options\niftyopt\venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo [ERROR] Python not found at %PYTHON%
    pause
    exit /b 1
)

:: Start the telegram engine (telethon)
"%PYTHON%" telegram_signal_engine.py

if errorlevel 1 (
    echo.
    echo [ERROR] Telegram engine exited with error code %errorlevel%
    pause
)
