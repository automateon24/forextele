@echo off
cls
echo ====================================================================
echo  FOREXTELE - 3-ENGINE SUITE START (AI-TUNED v2)
echo  Updated: 2026-10-03 - AI Audit Fixes Applied
echo ====================================================================
echo.
echo  ENGINE 1: BreakoutBoss (5 Models + Gann Harmonic)
echo    - H1 Trend Filter: ACTIVE (blocks counter-trend trades)
echo    - Blocked Hours: 05/09/18 UTC (0%% WR empirically)
echo    - Min Risk Floor: $1.20 (forces R:R at least 2.0)
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
start "MASTER_WATCHDOG" /MIN "%PYTHON%" "%DIR%\master_autostart_watchdog.py"
ping 127.0.0.1 -n 4 >nul

echo [%time%] Starting BreakoutBoss Engine (AI-tuned)...
start "BREAKOUTBOSS" /MIN "%PYTHON%" "%DIR%\breakout_boss_engine.py"
ping 127.0.0.1 -n 4 >nul

echo [%time%] Starting Autonomous AI SMC Scanner (with daily auto-tune)...
start "SMC_SCANNER" /MIN "%PYTHON%" "%DIR%\autonomous_ai_market_scanner.py"
ping 127.0.0.1 -n 4 >nul

echo [%time%] Starting Telegram VIP Signal Engine (whitelisted channels)...
start "TELEGRAM_SIGNALS" /MIN "%PYTHON%" "%DIR%\telegram_signal_engine.py"
ping 127.0.0.1 -n 6 >nul

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
