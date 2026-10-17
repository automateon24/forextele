@echo off
title FOREXTELE MASTER WATCHDOG LAUNCHER
cls
echo Starting ForexTele 24/7 Master Watchdog...
cd /d C:\anlyzeforex\forextele
start /B python master_production_watchdog.py
exit
