@echo off
REM Fix scheduled tasks to run only on weekdays (Mon-Fri)
echo === FIXING SCHEDULED TASKS TO WEEKDAYS ONLY ===

REM Delete existing tasks
schtasks /delete /tn "NiftyOpt_V3_Trader" /f 2>nul
schtasks /delete /tn "NiftyOpt_V4_Trader" /f 2>nul
schtasks /delete /tn "NiftyOpt_V4_Adaptive" /f 2>nul

echo Deleted old tasks...

REM Recreate V3 Trader - weekdays only at 9:15 AM
schtasks /create /tn "NiftyOpt_V3_Trader" /tr "C:\cursor\options\niftyopt\RUN_MODULAR_V3.bat" /sc WEEKLY /d MON,TUE,WED,THU,FRI /st 09:15 /ru "SYSTEM" /rl HIGHEST /f

echo Created V3 Trader (Mon-Fri 9:15 AM)...

REM Recreate V4 Trader - weekdays only at 9:15 AM  
schtasks /create /tn "NiftyOpt_V4_Trader" /tr "C:\cursor\options\niftyopt\RUN_MODULAR_V4.bat" /sc WEEKLY /d MON,TUE,WED,THU,FRI /st 09:15 /ru "SYSTEM" /rl HIGHEST /f

echo Created V4 Trader (Mon-Fri 9:15 AM)...

REM Recreate V4 Adaptive - weekdays only at 9:17 AM
schtasks /create /tn "NiftyOpt_V4_Adaptive" /tr "C:\cursor\options\niftyopt\START_ADAPTIVE_V4.bat" /sc WEEKLY /d MON,TUE,WED,THU,FRI /st 09:17 /ru "SYSTEM" /rl HIGHEST /f

echo Created V4 Adaptive (Mon-Fri 9:17 AM)...

echo.
echo === VERIFICATION ===
schtasks /query /tn "NiftyOpt_V3_Trader" /fo LIST | findstr "TaskName\|Schedule\|Start"
schtasks /query /tn "NiftyOpt_V4_Trader" /fo LIST | findstr "TaskName\|Schedule\|Start"
schtasks /query /tn "NiftyOpt_V4_Adaptive" /fo LIST | findstr "TaskName\|Schedule\|Start"

echo.
echo === DONE ===
pause
