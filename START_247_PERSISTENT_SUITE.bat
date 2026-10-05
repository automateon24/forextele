@echo off
cls
TITLE FOREXTELE 24/7 AUTONOMOUS SUITE
cd /d "%~dp0"

echo ====================================================================
echo  FOREXTELE - 24/7 AUTONOMOUS SUITE START (AUTO-HEALING AND BOOT)
echo  Runs continuously for the next 4 days until Friday market close!
echo  Auto-restarts on VPS reboot and self-heals any process drop.
echo ====================================================================
echo.

set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe

echo [1/3] Registering Windows Auto-Start on System Boot...
schtasks /create /tn "Forextele_Boot_AutoStart" /tr "\"%PYTHON_EXE%\" \"C:\anlyzeforex\forextele\start_watchdog_persistent.py\"" /sc ONSTART /rl HIGHEST /ru SYSTEM /f >nul 2>&1
echo   [OK] Boot task registered: Forextele_Boot_AutoStart (triggers on every VPS reboot).

echo.
echo [2/3] Registering 24/7 Persistent Watchdog Supervisor...
schtasks /create /tn "Forextele_247_Persistent_Watchdog" /tr "\"%PYTHON_EXE%\" \"C:\anlyzeforex\forextele\start_watchdog_persistent.py\"" /sc MINUTE /mo 5 /rl HIGHEST /f >nul 2>&1
echo   [OK] 5-minute supervisor task registered: Forextele_247_Persistent_Watchdog.

echo.
echo [3/3] Launching Master Watchdog and 3 Trading Engines as Detached Daemons...
"%PYTHON_EXE%" start_watchdog_persistent.py

echo.
echo Waiting 8 seconds for all engines to initialize...
ping 127.0.0.1 -n 9 >nul

echo.
echo ====================================================================
echo  [OK] ALL 3 ENGINES AND MASTER WATCHDOG ARE NOW ACTIVE AND PROTECTED!
echo.
echo  Engines Running:
echo    [1] BreakoutBoss v2 (5 Models + TSL Ratchet on Gold)
echo    [2] Autonomous SMC AI (Institutional M15 FVG / Order Block)
echo    [3] Telegram Signal Engine (40+ VIP Channels + AI Swarm)
echo    [4] 24/7 Autostart Watchdog (Survives reboots, crashes and disconnects)
echo.
echo  Monitor Live Logs in C:\anlyzeforex\forextele\logs\
echo ====================================================================
echo.
pause
