# PowerShell Script to Configure Unified Scheduled Tasks for NiftyOpt Trading Engine
# Prevents duplication, sets correct working directories, and disables idle/battery limits.

$ErrorActionPreference = "SilentlyContinue"

# 1. Clean up old legacy and temporary tasks
$tasksToDelete = @(
    "ModularTraderV3",
    "NiftyTrader_V4",
    "NiftyAdaptive_V4",
    "NiftyLiveTrading",
    "TestAdminTask",
    "TestSystemBatchRun",
    "TestSystemRun"
)

Write-Host "=== Cleaning up legacy and duplicate tasks ===" -ForegroundColor Yellow
foreach ($tn in $tasksToDelete) {
    if (Get-ScheduledTask -TaskName $tn) {
        Unregister-ScheduledTask -TaskName $tn -Confirm:$false
        Write-Host "Deleted task: $tn" -ForegroundColor Green
    }
}

# 2. Define task parameters
$workDir = "C:\cursor\options\niftyopt"
$user = "Administrator"

# Task 1: Token Refresh (Daily at 8:30 AM)
$tokenAction = New-ScheduledTaskAction -Execute "C:\cursor\options\niftyopt\DAILY_AUTO_LOGIN.bat" -WorkingDirectory $workDir
# Daily trigger starting today at 8:30 AM
$tokenTrigger = New-ScheduledTaskTrigger -Daily -At 08:30
$tokenSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew

# Task 2: V3 Trader (Mon-Fri at 9:15 AM)
$v3Action = New-ScheduledTaskAction -Execute "C:\cursor\options\niftyopt\RUN_MODULAR_V3.bat" -WorkingDirectory $workDir
$v3Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 09:15
$v3Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 7 -Minutes 30) -MultipleInstances IgnoreNew

# Task 3: V4 Trader (Mon-Fri at 9:15 AM)
$v4Action = New-ScheduledTaskAction -Execute "C:\cursor\options\niftyopt\RUN_MODULAR_V4.bat" -WorkingDirectory $workDir
$v4Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 09:15
$v4Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 7 -Minutes 30) -MultipleInstances IgnoreNew

# Task 4: V4 Adaptive (Mon-Fri at 9:17 AM)
$adaptiveAction = New-ScheduledTaskAction -Execute "C:\cursor\options\niftyopt\START_ADAPTIVE_V4.bat" -WorkingDirectory $workDir
$adaptiveTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 09:17
$adaptiveSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 7 -Minutes 30) -MultipleInstances IgnoreNew

Write-Host "`n=== Registering Unified NiftyOpt Production Tasks ===" -ForegroundColor Yellow

# Register Token Refresh
Register-ScheduledTask -TaskName "NiftyOpt_TokenRefresh" -Action $tokenAction -Trigger $tokenTrigger -Settings $tokenSettings -User $user -RunLevel Highest -Force
Write-Host "Registered: NiftyOpt_TokenRefresh (Daily 8:30 AM)" -ForegroundColor Green

# Register V3 Trader
Register-ScheduledTask -TaskName "NiftyOpt_V3_Trader" -Action $v3Action -Trigger $v3Trigger -Settings $v3Settings -User $user -RunLevel Highest -Force
Write-Host "Registered: NiftyOpt_V3_Trader (Mon-Fri 9:15 AM)" -ForegroundColor Green

# Register V4 Trader
Register-ScheduledTask -TaskName "NiftyOpt_V4_Trader" -Action $v4Action -Trigger $v4Trigger -Settings $v4Settings -User $user -RunLevel Highest -Force
Write-Host "Registered: NiftyOpt_V4_Trader (Mon-Fri 9:15 AM)" -ForegroundColor Green

# Register V4 Adaptive
Register-ScheduledTask -TaskName "NiftyOpt_V4_Adaptive" -Action $adaptiveAction -Trigger $adaptiveTrigger -Settings $adaptiveSettings -User $user -RunLevel Highest -Force
Write-Host "Registered: NiftyOpt_V4_Adaptive (Mon-Fri 9:17 AM)" -ForegroundColor Green

Write-Host "`n=== Task Configuration Completed Successfully ===" -ForegroundColor Cyan
