import subprocess

def setup_task():
    ps_cmd = r'''
$taskName = "Forex_Telegram_247_AutoStart"

# Unregister if already exists
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument '/c start "" "C:\anlyzeforex\forextele\run_telegram_gold_live.bat"'
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId "Administrator" -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings

Write-Host "Scheduled task $taskName registered successfully!"
'''
    ps_file = r"C:\anlyzeforex\forextele\scratch\make_task.ps1"
    with open(ps_file, "w", encoding="utf-8") as f:
        f.write(ps_cmd)
        
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file], capture_output=True, text=True)
    print("STDOUT:", res.stdout)
    print("STDERR:", res.stderr)

if __name__ == "__main__":
    setup_task()
