@echo off
TITLE START FOREXTELE AUTONOMOUS ENGINES (24/7 LIVE - $7,000 CAPITAL POOL)
COLOR 0A
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"

echo ====================================================================
echo    STARTING FOREXTELE AUTONOMOUS LIVE ENGINES ($7,000 CAPITAL POOL)
echo    1. Telegram VIP Signals Engine (40+ Channels with Trend Gate) [$1k]
echo    2. Autonomous AI Market Scanner (SMC + Liquidity Gate) [$1k]
echo    3. BreakoutBoss 5-Model Suite (M0, M1, M2, M3, M4) [$5k]
echo    4. Master 24/7 Autostart Watchdog (Reboot and Crash Supervisor)
echo ====================================================================
echo.

set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=py -3.11

:: 1. Verify MT5 Terminal is running
tasklist /fi "imagename eq terminal64.exe" | findstr /i "terminal64.exe" >nul
if %errorlevel% neq 0 (
    echo [MT5] XM Global MT5 terminal not running. Launching terminal64.exe...
    if exist "C:\Program Files\XM Global MT5\terminal64.exe" (
        start "" "C:\Program Files\XM Global MT5\terminal64.exe"
        ping 127.0.0.1 -n 7 >nul
    )
) else (
    echo [MT5] XM Global MT5 terminal is active and connected.
)

:: 2. Launch Telegram Signal Engine in Dedicated Window
echo [1/4] Launching Telegram Signal Engine (40+ VIP Channels)...
start "TELEGRAM_SIGNAL_ENGINE_247" cmd.exe /c "run_telegram_gold_live.bat"
ping 127.0.0.1 -n 4 >nul

:: 3. Launch Autonomous AI Market Scanner in Dedicated Window
echo [2/4] Launching Autonomous AI Market Scanner (GOLD and BTCUSD)...
start "AUTONOMOUS_AI_MARKET_SCANNER_247" cmd.exe /c "run_autonomous_scanner.bat"
ping 127.0.0.1 -n 4 >nul

:: 4. Launch BreakoutBoss 5-Model Multi-Session Gold Suite in Dedicated Window
echo [3/4] Launching BreakoutBoss 5-Model Suite (M0, M1, M2, M3, M4)...
start "BREAKOUT_BOSS_ENGINE_247" cmd.exe /c "run_breakout_boss.bat"
ping 127.0.0.1 -n 4 >nul

:: 5. Launch Master Autostart Watchdog in Dedicated Window
echo [4/4] Launching Master 24/7 Autostart Watchdog...
start "FOREXTELE_MASTER_WATCHDOG_247" cmd.exe /c "master_autostart_watchdog.bat"
ping 127.0.0.1 -n 3 >nul

echo.
echo ====================================================================
echo ALL 7 ALLOCATION BASKETS RUNNING IN PARALLEL
echo --------------------------------------------------------------------
echo  - Telegram Listener : Armed with H1 Trend Confluence Gate ($1k Basket)
echo  - AI Market Scanner : Cooldown 60m, Max 4 trades/day ($1k Basket)
echo  - BreakoutBoss M0-M4: 5 Compounding Models x 6 Global Sessions ($5k Baskets)
echo  - Master Watchdog   : Monitoring every 60s for 24/7 uptime
echo ====================================================================
echo.
ping 127.0.0.1 -n 5 >nul
