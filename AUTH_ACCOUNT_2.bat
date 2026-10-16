@echo off
TITLE TELEGRAM ACCOUNT 2 RE-AUTHENTICATION WIZARD
COLOR 0B
chcp 65001 > nul
cd /d "C:\anlyzeforex\forextele"

set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

echo ====================================================================
echo  TELEGRAM ACCOUNT 2 AUTHENTICATION (RESTORE ELITE WINNING CHANNELS)
echo  Target Channels: Market Trader, Perfect Management, Karol,
echo                  Josefina, Profitway, SureShot
echo ====================================================================
echo.

"%PYTHON_EXE%" reauth_account2.py

echo.
echo ====================================================================
echo  Authentication completed.
echo  Restarting Telegram Signal Engine with both accounts active...
echo ====================================================================

"%PYTHON_EXE%" -c "import psutil; [p.kill() for p in psutil.process_iter() if 'telegram_signal_engine' in ' '.join(p.cmdline() or []) and 'SepPro' not in ' '.join(p.cmdline() or [])]" 2>nul

echo Done! The Master Watchdog will auto-resume live listening in 30s.
pause
