@echo off
title FOREXTELE 24/7 LIVE ENGINE MONITOR
color 0A
cls
echo ===============================================================================
echo                FOREXTELE 24/7 LIVE ENGINE REAL-TIME MONITOR
echo ===============================================================================
echo  Press Ctrl+C to exit monitor (Engine will keep running in the background)
echo ===============================================================================
echo.

powershell -NoExit -Command "Get-Content -Path 'C:\anlyzeforex\forextele\logs\aio_live_engine.log' -Wait -Tail 40"
pause
