@echo off
echo.
echo ================================================================
echo  MODULAR TRADER V4 - APRIL 30 LEARNING IMPLEMENTATION
echo ================================================================
echo  Version: V4.0  Build Date: 2026-04-30
echo  V4: EOD Guard + Gap Recovery + Magic Cap3 + Bias Flip
echo ================================================================
echo.

:: Force working directory to project root (critical when double-clicked)
cd /d "c:\cursor\options\niftyopt"

:: Use full absolute Python path - NEVER relies on PATH or venv activation
set PYTHON=c:\cursor\options\niftyopt\venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo [ERROR] Python not found at %PYTHON%
    echo [ERROR] Virtual environment missing - please recreate venv
    pause
    exit /b 1
)
echo [PREFLIGHT] Python found: %PYTHON%

:: Run pre-flight checks
echo [PREFLIGHT] Running V4 test suite...
"%PYTHON%" tests\test_modular_trader_v4.py > test_v4_output.txt 2>&1
if errorlevel 1 (
    echo [PREFLIGHT] ❌ V4 tests failed - Review test_v4_output.txt
    type test_v4_output.txt
    pause
    exit /b 1
)
echo [PREFLIGHT] ✅ V4 tests passed - Ready for trading
echo.

:: Check for token file
if not exist "config\dhan_tokens.json" (
    echo [ERROR] ❌ config\dhan_tokens.json not found!
    echo [ERROR] Please run token refresh first
    pause
    exit /b 1
)
echo [PREFLIGHT] ✅ API tokens found
echo.

:: Create daily data directory
if not exist "daily_data" mkdir daily_data

:: Set log file name for today using PowerShell (reliable across locales)
for /f %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set mydate=%%a
echo [INFO] Logs will be saved to: daily_data\modular_%mydate%.log
echo.

echo ================================================================
echo  STARTING V4 TRADING ENGINE
echo ================================================================
echo.
echo Press Ctrl+C to stop at any time
echo.

:: Run V4
"%PYTHON%" MODULAR_TRADER_V4.py

:: If crash, log it
if errorlevel 1 (
    echo.
    echo [ERROR] V4 crashed unexpectedly!
    echo [ERROR] Check logs in daily_data folder
    echo.
    pause
)

:: No deactivate needed - we used full path, not venv activation
