@echo off
chcp 65001 >nul
title STRAGY V15 - LIVE ENGINE (25-Strategy Multi-Index)

:: ================================================================
::  STRAGY V15 PRODUCTION ENGINE LAUNCHER
::  Strategies : 36 strategies x 4 indices (NIFTY/BN/FN/SENSEX)
::  Capital    : Rs. 5,00,000 (5 Lakhs)
::  Run window : Mon-Fri 09:10 AM auto-start | 03:30 PM auto-stop
::  Logs       : C:\cursor\options\niftyopt\data\live_portfolio_trader.log
:: ================================================================

set PROJECT=c:\25stragy
set NIFTY_DIR=c:\cursor\options\niftyopt
set PYTHON=%NIFTY_DIR%\venv\Scripts\python.exe
set SCRIPT=%PROJECT%\engine_v15.py

:: FORCE WORKING DIRECTORY TO NIFTYOPT
cd /d "%NIFTY_DIR%"

:: ---- PYTHON CHECK ----
if not exist "%PYTHON%" (
    echo.
    echo [CRITICAL] Python not found at:
    echo   %PYTHON%
    echo.
    echo The virtual environment is missing. Please recreate it.
    pause
    exit /b 1
)

:: ---- SCRIPT CHECK ----
if not exist "%SCRIPT%" (
    echo.
    echo [CRITICAL] LIVE_PORTFOLIO_TRADER.py not found at:
    echo   %SCRIPT%
    pause
    exit /b 1
)

:: ---- TOKEN CHECK ----
if not exist "%NIFTY_DIR%\config\dhan_tokens.json" (
    echo.
    echo [CRITICAL] API token file missing:
    echo   %NIFTY_DIR%\config\dhan_tokens.json
    echo.
    echo Task Scheduler should have refreshed it at 8:30 AM.
    echo Check DAILY_AUTO_LOGIN.bat logs.
    pause
    exit /b 1
)

:: ---- ENSURE LOG DIRECTORY EXISTS ----
if not exist "%NIFTY_DIR%\data" mkdir "%NIFTY_DIR%\data"

:: ---- STARTUP BANNER ----
echo.
echo ========================================================================
echo   STRAGY V15 PRODUCTION ENGINE (LIVE PORTFOLIO TRADER)
echo   Python  : %PYTHON%
echo   Script  : %SCRIPT%
echo   Logs    : %NIFTY_DIR%\data\live_portfolio_trader.log
echo   Capital : Rs. 5,00,000
echo ========================================================================
echo.
echo   Indices   : NIFTY / BANKNIFTY / FINNIFTY / SENSEX
echo   Strategies: 36 active (MOMENTUM_BURST, MACD_DIV, ATR_BREAK, ...)
echo   Entry end : 13:00 tiered cutoff
echo   EOD exit  : 14:30 hard exit
echo.
echo   Press Ctrl+C to stop manually at any time
echo ========================================================================
echo.

:: ---- RUN TELEGRAM SIGNAL ENGINE (BACKGROUND) ----
echo Starting Telegram Signal Engine in the background...
start "Telegram AI Engine" cmd /c ""%PYTHON%" "%PROJECT%\telegram_signal_engine.py""

:: ---- RUN STRAGY V15 LIVE TRADER ----
:START_ENGINE
"%PYTHON%" "%SCRIPT%"
set EXIT_CODE=%errorlevel%

:: ---- SESSION ENDED ----
echo.
echo ========================================================================
if %EXIT_CODE% EQU 0 (
    echo   SESSION ENDED CLEANLY  ^|  Code: 0
    echo   Not restarting because exit was clean (end of day).
    pause
    exit /b 0
) else (
    echo   SESSION CRASHED WITH ERROR CODE: %EXIT_CODE%
    echo   Check logs: %NIFTY_DIR%\data\live_portfolio_trader.log
    echo   ========================================================================
    echo.
    echo   [CRITICAL] Auto-Restarting engine in 15 seconds to recover...
    timeout /t 15 /nobreak
    goto START_ENGINE
)
