@echo off
TITLE PURE GOLD & MULTI-ASSET TELEGRAM TO MT5 LIVE RUNNER
COLOR 0A
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: Use full Python 3.11 path to avoid py launcher issues
set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe

:: Fallback to py launcher if full path not found
if not exist "%PYTHON_EXE%" set PYTHON_EXE=py -3.11

cls

echo ====================================================================
echo    AUTONOMOUS TELEGRAM TO MT5 LIVE ENGINE WITH DYNAMIC AI TSL
echo ====================================================================
echo  Source           : Verified Dual-Account Telegram VIP Channels
echo  Execution Target : MetaTrader 5 (XM Global MT5 Live Direct)
echo  Magic Numbers    : 777777 (Gold), 888888 (Market Trader + Perfect Mgt)
echo  Encoding         : UTF-8 Enforced (Emoji and Multi-lingual Safe)
echo  ATR Gate         : Live M15 ATR-based SL cap + 1.5x R:R filter
echo  Supervisor Loop  : Auto-Restart on Connection Drops (24/7 Live)
echo ====================================================================
echo.

cd /d "%~dp0"

:: Create logs directory if missing
if not exist "logs" mkdir logs

:: Kill any stale forextele python instances before starting fresh
for /f "tokens=1" %%p in ('wmic process where "commandline like '%%telegram_signal_engine%%' and not commandline like '%%SepPro%%'" get processid ^| findstr /r "[0-9]"') do (
    taskkill /PID %%p /F >nul 2>&1
)
timeout /t 2 /nobreak >nul

:RUN_LOOP
echo [%DATE% %TIME%] Starting Telegram Listener Session... >> logs\telegram_gold_supervisor.log
echo [%DATE% %TIME%] Telegram Engine ACTIVE. Listening for Signals...
echo.

:: Run with full Python path and UTF-8 encoding
"%PYTHON_EXE%" -u telegram_signal_engine.py

echo.
echo ====================================================================
echo [WARNING] Telegram Listener disconnected at %DATE% %TIME%.
echo Restarting in 8 seconds... (Press Ctrl+C to stop)
echo ====================================================================
echo [%DATE% %TIME%] Telegram Listener EXITED. Auto-restarting in 8 seconds... >> logs\telegram_gold_supervisor.log

timeout /t 8 /nobreak >nul
goto RUN_LOOP
