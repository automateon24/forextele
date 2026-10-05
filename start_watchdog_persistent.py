"""
START PERSISTENT DETACHED WATCHDOG FOR FOREXTELE
================================================
Spawns master_autostart_watchdog.py as an independent, detached Windows daemon.
Ensures MT5 and all 3 Forex engines run 24/7 continuously, surviving RDP disconnects,
window closures, and system reboots.
"""

import sys
import os
import subprocess
import socket
from pathlib import Path

# Windows console UTF-8 standard
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
PYTHON_EXE = Path(r"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe")
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)

WATCHDOG_SCRIPT = BASE_DIR / "master_autostart_watchdog.py"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
WATCHDOG_LOG = LOGS_DIR / "master_autostart_watchdog.log"

# Single-instance check via socket port 39888
SOCKET_PORT = 39888
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.bind(('127.0.0.1', SOCKET_PORT))
    # We will close the test socket right before spawning the child,
    # and the child master_autostart_watchdog.py will hold it.
    sock.close()
except OSError:
    print("[INFO] Forex Master Watchdog is ALREADY ACTIVE and running (Port 39888 locked). Exiting.")
    sys.exit(0)

# Detached flags: DETACHED_PROCESS (0x00000008) | CREATE_NEW_PROCESS_GROUP (0x00000200)
DETACHED_FLAGS = 0x00000008 | 0x00000200

p = subprocess.Popen(
    [str(PYTHON_EXE), str(WATCHDOG_SCRIPT)],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=DETACHED_FLAGS,
    close_fds=True,
    cwd=str(BASE_DIR)
)

print(f"[OK] Forex Master Watchdog spawned as independent Windows daemon (PID: {p.pid})")
print("All 3 trading engines + MT5 terminal will now run 24/7 without interruption!")
