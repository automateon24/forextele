@echo off
echo ==========================================
echo    RESTARTING ALL AUTOMATEON TRADING SERVERS
echo ==========================================

echo [1] Force Killing all Python processes...
taskkill /F /IM python.exe /T

echo [2] Starting V15 Trading Engine...
start "V15 Trading Engine" cmd /c "C:\cursor\options\niftyopt\venv\Scripts\python.exe C:\25stragy\v15_engine.py"
timeout /t 2 /nobreak >nul

echo [3] Starting Telegram Signal Engine...
start "Telegram Engine" cmd /c "C:\cursor\options\niftyopt\venv\Scripts\python.exe C:\25stragy\telegram_signal_engine.py"
timeout /t 2 /nobreak >nul

echo [4] Starting Dashboard Web Server...
start "Dashboard UI Server" cmd /c "C:\cursor\options\niftyopt\venv\Scripts\python.exe C:\cursor\options\niftyopt\dashboard_server.py"

echo ==========================================
echo    ALL SERVERS STARTED SUCCESSFULLY!
echo ==========================================
pause
