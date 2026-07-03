@echo off
title Unified Trading Dashboard
echo ================================================================
echo  Unified Trading Dashboard Workstation
echo ================================================================
echo  Starting dashboard_server.py using venv...
echo.

cd /d "C:\cursor\options\niftyopt"
set PYTHON=C:\cursor\options\niftyopt\venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo [ERROR] Python not found at %PYTHON%
    pause
    exit /b 1
)

:: Ensure log directory exists
if not exist "daily_data" mkdir daily_data

:: Open the default browser to the Dashboard URL automatically
echo Opening browser to http://127.0.0.1:8000 ...
start http://127.0.0.1:8000

:: Start the dashboard server
"%PYTHON%" dashboard_server.py

if errorlevel 1 (
    echo.
    echo [ERROR] Dashboard server exited with error code %errorlevel%
    pause
)
