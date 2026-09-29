$sh = New-Object -ComObject WScript.Shell
$startupPath = [System.Environment]::GetFolderPath('Startup')
$shortcutFile = Join-Path $startupPath 'Start_Forex_Telegram_Terminal.lnk'
if (Test-Path $shortcutFile) {
    $sc = $sh.CreateShortcut($shortcutFile)
    Write-Host "Target: $($sc.TargetPath)"
    Write-Host "Arguments: $($sc.Arguments)"
    Write-Host "WorkingDirectory: $($sc.WorkingDirectory)"
} else {
    Write-Host "Shortcut not found"
}
