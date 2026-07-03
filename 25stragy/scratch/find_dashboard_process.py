import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Search for python processes running dashboard_server
cmd = 'wmic process where "CommandLine like \'%dashboard_server.py%\'" get ProcessId,CommandLine'
try:
    out = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
    print(out)
except Exception as e:
    print("Error querying processes:", e)
