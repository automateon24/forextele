$wsh = New-Object -ComObject WScript.Shell
$startupPath = [System.Environment]::GetFolderPath('Startup')
$targetBat = "C:\anlyzeforex\forextele\master_autostart_watchdog.bat"
$workDir = "C:\anlyzeforex\forextele"

# 1. Update existing Start_Forex_Telegram_Terminal.lnk
$lnk1 = Join-Path $startupPath "Start_Forex_Telegram_Terminal.lnk"
$sc1 = $wsh.CreateShortcut($lnk1)
$sc1.TargetPath = $targetBat
$sc1.WorkingDirectory = $workDir
$sc1.Description = "ForexTele Master 24/7 Autostart Watchdog"
$sc1.Save()
Write-Host "Updated shortcut: $lnk1 -> $targetBat"

# 2. Also create dedicated Start_Forex_Master_247.lnk
$lnk2 = Join-Path $startupPath "Start_Forex_Master_247.lnk"
$sc2 = $wsh.CreateShortcut($lnk2)
$sc2.TargetPath = $targetBat
$sc2.WorkingDirectory = $workDir
$sc2.Description = "ForexTele Master 24/7 Autostart Watchdog"
$sc2.Save()
Write-Host "Created shortcut: $lnk2 -> $targetBat"
