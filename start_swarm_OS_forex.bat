@echo off
title FOREX & GOLD AUTONOMOUS TELEGRAM TO MT5 TERMINAL
color 0A
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo ==================================================================================
echo    INITIATING AUTONOMOUS PURE TELEGRAM TO MT5 ENGINE (GOLD + MULTI-ASSET)        
echo ==================================================================================
echo.
cd /d "%~dp0"
call "%~dp0run_telegram_gold_live.bat"
