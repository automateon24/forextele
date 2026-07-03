# Run this AFTER confirming 6:45 PM test works tonight
# Schedules visible windows at 9:15 AM tomorrow (May 1, 2026)

$workDir     = "c:\cursor\options\niftyopt"
$tomorrow915 = (Get-Date).Date.AddDays(1).AddHours(9).AddMinutes(15)
$tomorrow917 = $tomorrow915.AddMinutes(2)

Unregister-ScheduledTask -TaskName "NiftyTrader_V5"  -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "NiftyAdaptive_V4" -Confirm:$false -ErrorAction SilentlyContinue

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

# Task 1: V5 Trader at 9:15 AM - visible window, stays open with pause
$action1   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/k SCHED_TRADER_V5.bat" -WorkingDirectory $workDir
$trigger1  = New-ScheduledTaskTrigger -Once -At $tomorrow915
$settings1 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 8) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "NiftyTrader_V5" -Action $action1 -Trigger $trigger1 -Settings $settings1 -Principal $principal -Force

# Task 2: Adaptive Engine at 9:17 AM - visible window
$action2   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/k SCHED_ADAPTIVE_V4.bat" -WorkingDirectory $workDir
$trigger2  = New-ScheduledTaskTrigger -Once -At $tomorrow917
$settings2 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 8) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "NiftyAdaptive_V4" -Action $action2 -Trigger $trigger2 -Settings $settings2 -Principal $principal -Force

Write-Host "TOMORROW TASKS registered (visible window + pause on exit):"
Write-Host "  NiftyTrader_V5   -> $tomorrow915"
Write-Host "  NiftyAdaptive_V4 -> $tomorrow917"
