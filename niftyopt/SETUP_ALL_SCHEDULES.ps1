# ============================================================
#  MASTER SCHEDULER SETUP - ALL TRADING ENGINES
#  Run once as Administrator to configure all tasks
#  Schedule: Monday-Friday only | Runs forever until stopped
#  Next run: Monday 2026-06-22
# ============================================================

# --- COMMON SETTINGS ---
$WORKDIR  = "C:\cursor\options\niftyopt"
$DaysWeekdays = [Microsoft.Win32.TaskScheduler.DaysOfTheWeek]::Monday -bor
                [Microsoft.Win32.TaskScheduler.DaysOfTheWeek]::Tuesday -bor
                [Microsoft.Win32.TaskScheduler.DaysOfTheWeek]::Wednesday -bor
                [Microsoft.Win32.TaskScheduler.DaysOfTheWeek]::Thursday -bor
                [Microsoft.Win32.TaskScheduler.DaysOfTheWeek]::Friday

# Helper: create or update a scheduled task (Mon-Fri weekly)
function Set-TradingTask {
    param(
        [string]$TaskName,
        [string]$BatFile,
        [string]$StartTime,   # e.g. "08:30" "09:10"
        [string]$Description,
        [bool]$RunHidden = $true
    )

    Write-Host "`n[SETUP] $TaskName -> $BatFile @ $StartTime (Mon-Fri)" -ForegroundColor Cyan

    # Build the trigger: every week Mon-Fri at StartTime, starting next Monday
    $nextMonday = (Get-Date "2026-06-22 $StartTime`:00")

    # Build action
    if ($RunHidden) {
        $action = New-ScheduledTaskAction `
            -Execute "cmd.exe" `
            -Argument "/c `"$BatFile`" >> `"$WORKDIR\logs\task_$TaskName.log`" 2>&1" `
            -WorkingDirectory $WORKDIR
    } else {
        $action = New-ScheduledTaskAction `
            -Execute "cmd.exe" `
            -Argument "/c start `"`" `"$BatFile`"" `
            -WorkingDirectory $WORKDIR
    }

    # Weekly trigger Mon-Fri
    $trigger = New-ScheduledTaskTrigger `
        -Weekly `
        -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
        -At $nextMonday

    # Settings: run whether logged on or not, restart on failure
    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 8) `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 2) `
        -StartWhenAvailable `
        -WakeToRun $false `
        -MultipleInstances IgnoreNew

    # Principal: run as SYSTEM or current user with highest privilege
    $principal = New-ScheduledTaskPrincipal `
        -UserId "SYSTEM" `
        -LogonType ServiceAccount `
        -RunLevel Highest

    # Register (or overwrite if exists)
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "  [REPLACE] Old task removed" -ForegroundColor Yellow
    }

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description $Description `
        -Force | Out-Null

    $t = Get-ScheduledTask -TaskName $TaskName
    $i = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "  [OK] State: $($t.State) | Next Run: $($i.NextRunTime)" -ForegroundColor Green
}

Write-Host "============================================================" -ForegroundColor White
Write-Host "  TRADING ENGINE SCHEDULER SETUP" -ForegroundColor White
Write-Host "  Configuring ALL engines: Mon-Fri ONLY" -ForegroundColor White
Write-Host "  Next run date: Monday 2026-06-22" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor White

# Ensure logs folder exists
if (!(Test-Path "$WORKDIR\logs")) { New-Item -ItemType Directory -Path "$WORKDIR\logs" | Out-Null }

# ============================================================
# 1. TOKEN REFRESH  — 08:30 AM every weekday (runs first)
# ============================================================
Set-TradingTask `
    -TaskName    "NiftyOpt_TokenRefresh" `
    -BatFile     "$WORKDIR\DAILY_AUTO_LOGIN.bat" `
    -StartTime   "08:30" `
    -Description "Dhan API token refresh. Must complete before 09:10 AM traders start." `
    -RunHidden   $true

# ============================================================
# 2. V3 TRADER — 09:15 AM every weekday
# ============================================================
Set-TradingTask `
    -TaskName    "NiftyOpt_V3_Trader" `
    -BatFile     "$WORKDIR\RUN_MODULAR_V3.bat" `
    -StartTime   "09:15" `
    -Description "V3 Modular Trader: 18 strategies, live Dhan API, NIFTY multi-index." `
    -RunHidden   $false

# ============================================================
# 3. V4 TRADER — 09:15 AM every weekday
# ============================================================
Set-TradingTask `
    -TaskName    "NiftyOpt_V4_Trader" `
    -BatFile     "$WORKDIR\RUN_MODULAR_V4.bat" `
    -StartTime   "09:15" `
    -Description "V4 Modular Trader: EOD Guard + Gap Recovery + Magic Cap3 + Bias Flip." `
    -RunHidden   $false

# ============================================================
# 4. V4 ADAPTIVE ENGINE — 09:17 AM every weekday
# ============================================================
Set-TradingTask `
    -TaskName    "NiftyOpt_V4_Adaptive" `
    -BatFile     "$WORKDIR\START_ADAPTIVE_V4.bat" `
    -StartTime   "09:17" `
    -Description "V4 Adaptive Engine: self-learning regime detection and parameter tuning." `
    -RunHidden   $false

# ============================================================
# 5. STRAGY V15 (25-STRATEGY / NEW) — 09:20 AM every weekday
# ============================================================
Set-TradingTask `
    -TaskName    "NiftyOpt_Stragy_V15" `
    -BatFile     "$WORKDIR\RUN_STRAGY_V15.bat" `
    -StartTime   "09:20" `
    -Description "Stragy V15: 36 strategies x 4 indices (NIFTY/BN/FN/SENSEX). 5L capital." `
    -RunHidden   $false

# ============================================================
# 5b. UNIFIED DASHBOARD — 09:18 AM every weekday
# ============================================================
Set-TradingTask `
    -TaskName    "NiftyOpt_Unified_Dashboard" `
    -BatFile     "$WORKDIR\START_UNIFIED_DASHBOARD.bat" `
    -StartTime   "09:18" `
    -Description "Unified Trading Dashboard: Live Web UI for all engines." `
    -RunHidden   $true

# ============================================================
# 6. EOD SUMMARY — 15:30 PM every weekday
# ============================================================
Set-TradingTask `
    -TaskName    "NiftyOpt_EOD_Summary" `
    -BatFile     "$WORKDIR\EOD_SUMMARY.bat" `
    -StartTime   "15:30" `
    -Description "End-of-day summary: PnL report, adaptive learnings, token status check." `
    -RunHidden   $true

# ============================================================
# DISABLE OLD / DUPLICATE TASKS
# ============================================================
Write-Host "`n[CLEANUP] Disabling old/duplicate tasks..." -ForegroundColor Yellow
$oldTasks = @("DhanDailyTokenRefresh", "ModularTraderV3_Morning", "ModularTraderV3_Test", "V4_Paper_Trading")
foreach ($old in $oldTasks) {
    $t = Get-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue
    if ($t) {
        Disable-ScheduledTask -TaskName $old | Out-Null
        Write-Host "  [DISABLED] $old" -ForegroundColor DarkYellow
    }
}

# ============================================================
# VERIFICATION — Print final schedule
# ============================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor White
Write-Host "  FINAL SCHEDULE CONFIRMATION" -ForegroundColor White
Write-Host "  All times IST | Mon-Fri ONLY | Sat-Sun = NO TRADING" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor White

$tradingTasks = @(
    "NiftyOpt_TokenRefresh",
    "NiftyOpt_V3_Trader",
    "NiftyOpt_V4_Trader",
    "NiftyOpt_V4_Adaptive",
    "NiftyOpt_Unified_Dashboard",
    "NiftyOpt_Stragy_V15",
    "NiftyOpt_EOD_Summary"
)

$col1 = "{0,-28}" -f "Task Name"
$col2 = "{0,-10}" -f "Time"
$col3 = "{0,-10}" -f "State"
$col4 = "{0,-24}" -f "Next Run"
Write-Host "  $col1 $col2 $col3 $col4" -ForegroundColor White
Write-Host ("  " + "-" * 76)

foreach ($tn in $tradingTasks) {
    $t = Get-ScheduledTask -TaskName $tn -ErrorAction SilentlyContinue
    $i = Get-ScheduledTaskInfo -TaskName $tn -ErrorAction SilentlyContinue
    if ($t) {
        $startBound = $t.Triggers[0].StartBoundary
        $timeOnly   = if ($startBound) { ([datetime]$startBound).ToString("hh:mm tt") } else { "N/A" }
        $nextRun    = if ($i.NextRunTime) { $i.NextRunTime.ToString("ddd dd-MMM hh:mm tt") } else { "N/A" }
        $stateColor = if ($t.State -eq "Ready") { "Green" } else { "Red" }
        $c1 = "{0,-28}" -f $tn
        $c2 = "{0,-10}" -f $timeOnly
        $c3 = "{0,-10}" -f $t.State
        $c4 = "{0,-24}" -f $nextRun
        Write-Host "  $c1 $c2 " -NoNewline
        Write-Host "$c3 " -ForegroundColor $stateColor -NoNewline
        Write-Host "$c4"
    }
}

Write-Host ""
Write-Host "  [DONE] All trading tasks scheduled. System will auto-start Monday 09:10+" -ForegroundColor Green
Write-Host "  [INFO] Saturday & Sunday: NO tasks will run (weekday trigger only)" -ForegroundColor Cyan
Write-Host "  [INFO] To stop: schtasks /End /TN NiftyOpt_<name>" -ForegroundColor DarkCyan
Write-Host "  [INFO] To disable all: Run DISABLE_ALL_TRADING.ps1" -ForegroundColor DarkCyan
Write-Host ""
