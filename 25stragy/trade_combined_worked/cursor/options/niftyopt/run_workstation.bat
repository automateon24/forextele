@echo off
title All-Star V15 Trading Workstation Launcher
color 0B
cls
echo =======================================================================
echo          ALL-STAR V15 HYBRID PRODUCTION TRADING WORKSTATION            
echo =======================================================================
echo.
echo [1/3] Launching Live Trading Engine in PowerShell...
start powershell.exe -NoExit -Command "Set-Location 'C:\cursor\options\niftyopt'; Write-Host 'Starting All-Star V15 Trading Bot...' -ForegroundColor Green; & 'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe' LIVE_PORTFOLIO_TRADER.py"
timeout /t 2 /nobreak >nul

echo [2/3] Launching Workstation Dashboard Server in PowerShell...
start powershell.exe -NoExit -Command "Set-Location 'C:\cursor\options\niftyopt'; Write-Host 'Starting FastAPI Dashboard Server...' -ForegroundColor Cyan; & 'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe' dashboard_server.py"
timeout /t 4 /nobreak >nul

echo [3/3] Opening Web Interface...
start "" "http://127.0.0.1:8000"

echo.
echo =======================================================================
echo Workstation successfully launched! You can close this launcher window.
echo Both services are running independently in their PowerShell windows.
echo =======================================================================
timeout /t 5
