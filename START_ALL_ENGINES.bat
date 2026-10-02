@echo off
cls
echo ====================================================================
echo  FOREXTELE - 3-ENGINE SUITE START (AI-TUNED v2)
echo  Updated: 2026-10-03 | AI Audit Fixes Applied
echo ====================================================================
echo.
echo  ENGINE 1: BreakoutBoss (5 Models + Gann Harmonic)
echo    - H1 Trend Filter: ACTIVE (blocks counter-trend trades)
echo    - Blocked Hours: 05/09/18 UTC (0%% WR empirically)
echo    - Min Risk Floor: $1.20 (forces R:R >= 2.0)
echo.
echo  ENGINE 2: Autonomous AI Market Scanner (SMC)
echo    - Daily AI Auto-Tune: ACTIVE (adjusts thresholds at UTC midnight)
echo    - Max daily trades auto-adjusted by yesterday WR
echo.
echo  ENGINE 3: Telegram VIP Signal Engine
echo    - Profitable channel list: 19 channels whitelisted
echo    - Blacklisted: 4193 / 4177 / 4175 / 4155 / 4156
echo    - Max risk per trade: $50 (1%% of balance)
echo.
echo ====================================================================

SET PYTHON=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
SET DIR=C:\anlyzeforex\forextele

echo [%time%] Starting master watchdog...
start "MASTER_WATCHDOG" /MIN cmd /c "%PYTHON% %DIR%\master_autostart_watchdog.py >> %DIR%\logs\watchdog.log 2>&1"
timeout /t 3 /nobreak >nul

echo [%time%] Starting BreakoutBoss Engine (AI-tuned)...
start "BREAKOUTBOSS" /MIN cmd /c "%PYTHON% %DIR%\breakout_boss_engine.py >> %DIR%\logs\breakout_boss.log 2>&1"
timeout /t 3 /nobreak >nul

echo [%time%] Starting Autonomous AI SMC Scanner (with daily auto-tune)...
start "SMC_SCANNER" /MIN cmd /c "%PYTHON% %DIR%\autonomous_ai_market_scanner.py >> %DIR%\logs\smc_scanner.log 2>&1"
timeout /t 3 /nobreak >nul

echo [%time%] Starting Telegram VIP Signal Engine (whitelisted channels)...
start "TELEGRAM_SIGNALS" /MIN cmd /c "%PYTHON% %DIR%\telegram_signal_engine.py >> %DIR%\logs\telegram_signals.log 2>&1"
timeout /t 5 /nobreak >nul

echo.
echo ====================================================================
echo  ALL 3 ENGINES STARTED. Monitor logs in: %DIR%\logs\
echo  BreakoutBoss : logs\breakout_boss.log
echo  SMC Scanner  : logs\smc_scanner.log
echo  Telegram     : logs\telegram_signals.log
echo  Watchdog     : logs\watchdog.log
echo ====================================================================
echo.
pause
