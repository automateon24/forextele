@echo off
cls
echo ====================================================================
echo  FOREXTELE - MONDAY MARKET OPEN 3-ENGINE LIVE SUITE START
echo  Equipped with:
echo    [1] BreakoutBoss v2 (TSL Ratchet, H1 Trend Filter, 5 Compounding Models)
echo    [2] Autonomous SMC AI v2 (M15 FVG + Order Block Mitigation, 1:2.5+ R:R)
echo    [3] Telegram Signals Engine v2 (Whitelisted Channels, $50 Max Risk Cap)
echo    [4] AI Live Performance Watchdog (Continuous Backtest Alignment)
echo ====================================================================
echo.

cd /d "C:\anlyzeforex\forextele"
set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe

echo [1/4] Starting BreakoutBoss (5 Models + TSL)...
start "BREAKOUT_BOSS_ENGINE" "%PYTHON_EXE%" breakout_boss_engine.py

timeout /t 3 /nobreak >nul

echo [2/4] Starting Autonomous SMC AI (Institutional FVG/OB Engine)...
start "AUTONOMOUS_SMC_SCANNER" "%PYTHON_EXE%" autonomous_ai_market_scanner.py

timeout /t 3 /nobreak >nul

echo [3/4] Starting Telegram Signals Engine (Profitable Whitelist Only)...
start "TELEGRAM_SIGNAL_ENGINE" "%PYTHON_EXE%" telegram_signal_engine.py

timeout /t 3 /nobreak >nul

echo [4/4] Starting AI Live Performance Watchdog...
start "AI_ALIGNMENT_WATCHDOG" "%PYTHON_EXE%" ai_backtest_alignment_watchdog.py

echo.
echo ====================================================================
echo  ALL 3 PRODUCTION ENGINES + AI WATCHDOG ARE NOW RUNNING!
echo  Check live logs in C:\anlyzeforex\forextele\logs\
echo ====================================================================
exit
