@echo off
chcp 65001 >nul
title MODULAR TRADER V3 - LIVE

:: PERMANENT ABSOLUTE PATHS - NEVER CHANGE THESE
set PROJECT=c:\cursor\options\niftyopt
set PYTHON=%PROJECT%\venv\Scripts\python.exe
set SCRIPT=%PROJECT%\MODULAR_TRADER_V3.py

:: FORCE WORKING DIRECTORY
cd /d "%PROJECT%"

:: PYTHON CHECK - fail fast with clear message
if not exist "%PYTHON%" (
    echo.
    echo [CRITICAL] Python not found at:
    echo   %PYTHON%
    echo.
    echo The virtual environment is missing. Please recreate it.
    pause
    exit /b 1
)

:: SCRIPT CHECK
if not exist "%SCRIPT%" (
    echo.
    echo [CRITICAL] MODULAR_TRADER_V3.py not found at:
    echo   %SCRIPT%
    pause
    exit /b 1
)

:: TOKEN CHECK
if not exist "%PROJECT%\config\dhan_tokens.json" (
    echo.
    echo [CRITICAL] API token file missing:
    echo   %PROJECT%\config\dhan_tokens.json
    echo.
    echo Task Scheduler should have refreshed it at 8:30 AM.
    echo Check DAILY_AUTO_LOGIN.bat logs.
    pause
    exit /b 1
)

:: ENSURE LOG DIRECTORY EXISTS
if not exist "%PROJECT%\daily_data" mkdir "%PROJECT%\daily_data"

:: STARTUP BANNER
echo.
echo ========================================================================
echo   MODULAR TRADER V3  ^|  18 STRATEGIES  ^|  REAL DHAN API
echo   Python  : %PYTHON%
echo   Script  : %SCRIPT%
echo   Logs    : %PROJECT%\daily_data\v3_YYYYMMDD.log
echo   Capital : 18 x Rs.50,000 = Rs.9,00,000
echo ========================================================================
echo.
echo   Strategies: All 18 active (No ML / No Adaptive)
echo   Entry window: 9:30 AM - 2:30 PM
echo   EOD exit: 3:15 PM auto-forced
echo.
echo   Press Ctrl+C to stop manually at any time
echo ========================================================================
echo.

:: RUN V3
"%PYTHON%" "%SCRIPT%"
set EXIT_CODE=%errorlevel%

:: SESSION ENDED - SHOW SUMMARY THEN WAIT FOR KEY PRESS
echo.
echo ========================================================================
if %EXIT_CODE% EQU 0 (
    echo   SESSION ENDED CLEANLY
) else (
    echo   SESSION ENDED WITH ERROR CODE: %EXIT_CODE%
    echo   Check logs in: %PROJECT%\daily_data\
)
echo ========================================================================
echo.
echo   Review the P^&L summary above, then press any key to close.
echo.
pause
