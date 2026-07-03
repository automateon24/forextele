@echo off
chcp 65001 >nul
title MULTI-INDEX SCANNER V3  [*** LIVE ORDERS ***]

set PROJECT=c:\cursor\options\niftyopt
set PYTHON=%PROJECT%\venv\Scripts\python.exe
set SCRIPT=%PROJECT%\MULTI_INDEX_SCANNER_V3.py

cd /d "%PROJECT%"

if not exist "%PYTHON%" (
    echo [CRITICAL] Python venv not found at: %PYTHON%
    pause & exit /b 1
)
if not exist "%PROJECT%\config\dhan_tokens.json" (
    echo [CRITICAL] API token file missing: %PROJECT%\config\dhan_tokens.json
    pause & exit /b 1
)
if not exist "%PROJECT%\daily_data" mkdir "%PROJECT%\daily_data"

echo.
echo ============================================================
echo   MULTI-INDEX SCANNER V3  ^|  NIFTY / BANKNIFTY / FINNIFTY
echo                           ^|  MIDCPNIFTY / SENSEX
echo ============================================================
echo   *** LIVE MODE -- REAL ORDERS WILL BE PLACED ***
echo ============================================================
echo.
echo Press Ctrl+C within 5 seconds to abort...
timeout /t 5
echo.

"%PYTHON%" "%SCRIPT%" --live
echo.
echo Session ended. Press any key to close.
pause
