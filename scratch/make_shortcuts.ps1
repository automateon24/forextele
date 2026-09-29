
$WshShell = New-Object -ComObject WScript.Shell

$startupPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\Start_Forex_Telegram_Terminal.lnk"
$s1 = $WshShell.CreateShortcut($startupPath)
$s1.TargetPath = "C:\anlyzeforex\forextele\run_telegram_gold_live.bat"
$s1.WorkingDirectory = "C:\anlyzeforex\forextele"
$s1.Description = "Autonomous 24/7 Forex and Gold Telegram MT5 Terminal"
$s1.Save()

$desktopPath = Join-Path "C:\Users\Administrator\Desktop" "START_FOREX_TELEGRAM_TERMINAL.lnk"
$s2 = $WshShell.CreateShortcut($desktopPath)
$s2.TargetPath = "C:\anlyzeforex\forextele\run_telegram_gold_live.bat"
$s2.WorkingDirectory = "C:\anlyzeforex\forextele"
$s2.Description = "Autonomous 24/7 Forex and Gold Telegram MT5 Terminal"
$s2.Save()

Write-Host "SUCCESS: Shortcuts created in Startup folder and on Desktop!"
