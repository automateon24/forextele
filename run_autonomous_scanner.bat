@echo off
TITLE AUTONOMOUS AI MARKET SCANNER (SMC + LIQUIDITY + ML)
COLOR 0B
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=py -3.11

cls
echo ====================================================================
echo    AUTONOMOUS AI MARKET SCANNER (GOLD & BTCUSD SMC ENGINE)
echo ====================================================================
echo  Source           : Autonomous MT5 Live Chart Scanner (Zero Telegram Dependency)
echo  Patterns         : Oversold Sweeps + Bearish FVG + Trend Continuation
echo  Execution Target : MetaTrader 5 (XM Global Direct)
echo  Magic Number     : 999001
echo  TSL Rule         : Fixed SL until TP2 + 10-Pip Jumping TSL
echo  Supervisor Loop  : Auto-Restart on Exceptions (24/7 Live)
echo ====================================================================
echo.

cd /d "%~dp0"
if not exist "logs" mkdir logs

:RUN_LOOP
echo [%DATE% %TIME%] Starting Autonomous AI Market Scanner... >> logs\autonomous_scanner_supervisor.log
echo [%DATE% %TIME%] Autonomous Scanner ACTIVE. Scanning GOLD and BTCUSD...
echo.

"%PYTHON_EXE%" -u autonomous_ai_market_scanner.py

echo.
echo ====================================================================
echo [WARNING] Autonomous Scanner disconnected at %DATE% %TIME%.
echo Restarting in 5 seconds... (Press Ctrl+C to stop)
echo ====================================================================
echo [%DATE% %TIME%] Autonomous Scanner EXITED. Auto-restarting in 5 seconds... >> logs\autonomous_scanner_supervisor.log

ping 127.0.0.1 -n 6 >nul
goto RUN_LOOP
