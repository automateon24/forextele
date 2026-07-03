import subprocess
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

# 1. Find and kill all processes running dashboard_server.py
cmd_find = 'wmic process where "CommandLine like \'%dashboard_server.py%\'" get ProcessId'
try:
    out = subprocess.check_output(cmd_find, shell=True).decode('utf-8', errors='ignore')
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
            
    # Kill each PID
    for pid in pids:
        print(f"Killing process {pid}...")
        os.system(f"taskkill /F /PID {pid}")
except Exception as e:
    print("Error stopping old server processes:", e)

time.sleep(2)

# 2. Start the new server in the background
venv_python = r"C:\cursor\options\niftyopt\venv\Scripts\python.exe"
server_script = r"C:\cursor\options\niftyopt\dashboard_server.py"

print("Starting dashboard server...")
# Run as a background process
subprocess.Popen([venv_python, server_script], creationflags=subprocess.CREATE_NEW_CONSOLE)
print("Dashboard server started in a new background console.")
