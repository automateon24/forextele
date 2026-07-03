@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================================
echo  ADAPTIVE ENGINE V4 - Adaptive Trading Layer
echo  Phase A: Rule-Based Foundation
echo ============================================================
echo.
echo  This runs PARALLEL to MODULAR_TRADER_V4.py
echo  - Monitors V4 performance in real-time
echo  - Detects market regime (Trending/Range/Volatile/Quiet)
echo  - Auto-adjusts thresholds every 15 minutes
echo  - NO RESTART of V4 required
echo.
echo ============================================================
echo.

:: Use FULL ABSOLUTE path - never depends on working directory or PATH
set PYTHON_EXE=c:\cursor\options\niftyopt\venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found at %PYTHON_EXE%
    echo Please ensure virtual environment exists at c:\cursor\options\niftyopt\venv
    pause
    exit /b 1
)

:: Also force working directory to project root (needed when bat is double-clicked)
cd /d "c:\cursor\options\niftyopt"

echo [OK] Python found: %PYTHON_EXE%
echo.

:: Create adaptive_data directory if not exists
if not exist "adaptive_data" (
    echo [INIT] Creating adaptive_data directory...
    mkdir adaptive_data
)

:: Check if V4 is running (optional warning)
tasklist | findstr "python.exe" >nul
if errorlevel 1 (
    echo [WARNING] MODULAR_TRADER_V4.py does not appear to be running
    echo [WARNING] Adaptive Engine works best when V4 is active
    echo.
    choice /C YN /M "Continue anyway?"
    if errorlevel 2 exit /b 1
    echo.
)

:: Display startup info
echo [START] Launching Adaptive Engine V4...
echo [INFO] Log file: adaptive_data/adaptive_engine.log
echo [INFO] Config file: adaptive_data/adaptive_config.json
echo [INFO] Database: adaptive_data/performance.db
echo.
echo ============================================================
echo  PRESS CTRL+C TO STOP
echo ============================================================
echo.

:: Run the adaptive engine
%PYTHON_EXE% ADAPTIVE_V4.py

:: If engine exits, show status
echo.
echo ============================================================
echo  ADAPTIVE ENGINE STOPPED
echo ============================================================
echo.
echo Check logs: adaptive_data/adaptive_engine.log
echo Check config: adaptive_data/adaptive_config.json
echo.

pause
