# Schedule V3 and V4 for tomorrow (June 3, 2026)
# Run this after confirming today is June 2nd and fixes are applied

$workDir = "c:\cursor\options\niftyopt"

# June 3, 2026 schedule
$june3_915 = Get-Date -Year 2026 -Month 6 -Day 3 -Hour 9 -Minute 15
$june3_916 = $june3_915.AddMinutes(1)
$june3_917 = $june3_915.AddMinutes(2)

# Remove any existing tasks
Unregister-ScheduledTask -TaskName "NiftyTrader_V3_June3" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "NiftyTrader_V4_June3" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "NiftyAdaptive_V4_June3" -Confirm:$false -ErrorAction SilentlyContinue

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

# Task 1: V3 at 9:15 AM
$action1   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/k RUN_MODULAR_V3.bat" -WorkingDirectory $workDir
$trigger1  = New-ScheduledTaskTrigger -Once -At $june3_915
$settings1 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 8) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "NiftyTrader_V3_June3" -Action $action1 -Trigger $trigger1 -Settings $settings1 -Principal $principal -Force

# Task 2: V4 at 9:16 AM (1 minute after V3)
$action2   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/k RUN_MODULAR_V4.bat" -WorkingDirectory $workDir
$trigger2  = New-ScheduledTaskTrigger -Once -At $june3_916
$settings2 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 8) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "NiftyTrader_V4_June3" -Action $action2 -Trigger $trigger2 -Settings $settings2 -Principal $principal -Force

# Task 3: Adaptive V4 at 9:17 AM (2 minutes after V3)
$action3   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/k START_ADAPTIVE_V4.bat" -WorkingDirectory $workDir
$trigger3  = New-ScheduledTaskTrigger -Once -At $june3_917
$settings3 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 8) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "NiftyAdaptive_V4_June3" -Action $action3 -Trigger $trigger3 -Settings $settings3 -Principal $principal -Force

Write-Host "=========================================="
Write-Host "JUNE 3, 2026 TRADING SCHEDULED"
Write-Host "=========================================="
Write-Host ""
Write-Host "FIXES APPLIED:"
Write-Host "  - Magic Square: Flat gap day blocking (<0.15%)"
Write-Host "  - Magic Square: Early enabled check (prevents trades after disabled)"
Write-Host "  - SCALPING: Afternoon block after 14:00 (both V3 & V4)"
Write-Host "  - SCALPING: Tightened day_move filter 80->30pts (V4)"
Write-Host "  - PUT_WRITER_SUPPORT: Morning direction guard (spot > open - 25pts)"
Write-Host "  - V4: Session summary logging added"
Write-Host "  - TIME_STOP: 120 minutes (both)"
Write-Host "  - MAGIC_MAX_TRADES: 2 (both)"
Write-Host "  - AI threshold: 0.80 (both)"
Write-Host ""
Write-Host "SCHEDULE:"
Write-Host "  V3       -> $june3_915 (18 strategies)"
Write-Host "  V4       -> $june3_916 (V4 + Adaptive ML)"
Write-Host "  ADAPTIVE -> $june3_917 (Learning engine)"
Write-Host ""
Write-Host "=========================================="
