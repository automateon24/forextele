@echo off
cls
echo ============================================================
echo    SCHEDULED TASKS VERIFICATION REPORT
echo    Date: %date% %time%
echo ============================================================
echo.

echo [1] NiftyOpt_V3_Trader
echo ------------------------------------------------------------
schtasks /query /tn "NiftyOpt_V3_Trader" /fo LIST 2>&1 | findstr /I "TaskName\|Schedule\|Start Time\|Status\|Last\|Next"
echo.

echo [2] NiftyOpt_V4_Trader
echo ------------------------------------------------------------
schtasks /query /tn "NiftyOpt_V4_Trader" /fo LIST 2>&1 | findstr /I "TaskName\|Schedule\|Start Time\|Status\|Last\|Next"
echo.

echo [3] NiftyOpt_V4_Adaptive
echo ------------------------------------------------------------
schtasks /query /tn "NiftyOpt_V4_Adaptive" /fo LIST 2>&1 | findstr /I "TaskName\|Schedule\|Start Time\|Status\|Last\|Next"
echo.

echo [4] NiftyOpt_TokenRefresh
echo ------------------------------------------------------------
schtasks /query /tn "NiftyOpt_TokenRefresh" /fo LIST 2>&1 | findstr /I "TaskName\|Schedule\|Start Time\|Status\|Last\|Next"
echo.

echo ============================================================
echo    VERIFICATION COMPLETE
echo ============================================================
pause
