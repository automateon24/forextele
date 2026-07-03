@echo off
REM ============================================================
REM  Dhan Daily Token Refresh - PERMANENT BULLETPROOF VERSION
REM  - Finds Python dynamically (never hardcoded path)
  REM  - Auto-installs missing packages
REM  - Sends Telegram alert on ANY failure
REM  - Logs every step with timestamp
REM ============================================================

set WORKDIR=C:\cursor\options\niftyopt
set LOGFILE=%WORKDIR%\logs\scheduler.log
set VENV_PYTHON=%WORKDIR%\venv\Scripts\python.exe

cd /d %WORKDIR%
if not exist "%WORKDIR%\logs" mkdir "%WORKDIR%\logs"

echo [%date% %time%] ========== DAILY TOKEN REFRESH START ========== >> %LOGFILE%

REM ── Step 1: Find Python - venv first, then system fallback ──────────────────
set PYTHON=

if exist "%VENV_PYTHON%" (
    set PYTHON=%VENV_PYTHON%
    echo [%date% %time%] Python: VENV found at %VENV_PYTHON% >> %LOGFILE%
    goto :python_found
)

REM Venv missing - find any working Python on this machine
for %%P in (
    "C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
    "C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"
    "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%P (
        set PYTHON=%%P
        echo [%date% %time%] Python: SYSTEM found at %%P >> %LOGFILE%
        goto :python_found
    )
)

REM No Python found at all
echo [%date% %time%] FATAL: No Python found anywhere on this machine >> %LOGFILE%
echo [%date% %time%] Send Telegram alert manually: Token refresh failed - Python missing >> %LOGFILE%
powershell -NoProfile -Command "Invoke-RestMethod -Uri 'https://api.telegram.org/bot8716774883:AAFbzhRN8uZPdwCEmUwoepXR1D4BlmZThKA/sendMessage' -Method POST -Body @{chat_id='1437833304'; text='CRITICAL: Token refresh FAILED - Python not found on machine. Manual login required.'} -ContentType 'application/x-www-form-urlencoded'" >> %LOGFILE% 2>&1
exit /b 1

:python_found
echo [%date% %time%] Using Python: %PYTHON% >> %LOGFILE%

REM ── Step 2: Auto-install missing packages ───────────────────────────────────
%PYTHON% -c "import pyotp, yaml, requests" > nul 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] Missing packages - auto-installing... >> %LOGFILE%
    %PYTHON% -m pip install pyotp pyyaml requests --quiet >> %LOGFILE% 2>&1
    echo [%date% %time%] Packages installed >> %LOGFILE%
)

REM ── Step 3: Verify required files ───────────────────────────────────────────
if not exist "%WORKDIR%\dhan_direct_auth.py" (
    echo [%date% %time%] FATAL: dhan_direct_auth.py missing >> %LOGFILE%
    powershell -NoProfile -Command "Invoke-RestMethod -Uri 'https://api.telegram.org/bot8716774883:AAFbzhRN8uZPdwCEmUwoepXR1D4BlmZThKA/sendMessage' -Method POST -Body @{chat_id='1437833304'; text='CRITICAL: dhan_direct_auth.py missing. Token refresh FAILED.'} -ContentType 'application/x-www-form-urlencoded'" >> %LOGFILE% 2>&1
    exit /b 1
)
echo [%date% %time%] All files OK >> %LOGFILE%

REM ── Step 4: Run token refresh ───────────────────────────────────────────────
echo [%date% %time%] Running token refresh... >> %LOGFILE%
%PYTHON% "%WORKDIR%\dhan_direct_auth.py" force >> %LOGFILE% 2>&1

if %errorlevel% == 0 (
    echo [%date% %time%] ========== TOKEN REFRESH SUCCESS ========== >> %LOGFILE%
) else (
    echo [%date% %time%] ========== TOKEN REFRESH FAILED - Sending Telegram alert ========== >> %LOGFILE%
    powershell -NoProfile -Command "Invoke-RestMethod -Uri 'https://api.telegram.org/bot8716774883:AAFbzhRN8uZPdwCEmUwoepXR1D4BlmZThKA/sendMessage' -Method POST -Body @{chat_id='1437833304'; text='CRITICAL: Dhan token refresh FAILED at 8:30 AM. Manual login needed NOW before market opens.'} -ContentType 'application/x-www-form-urlencoded'" >> %LOGFILE% 2>&1
    exit /b 1
)
