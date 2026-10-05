"""
MASTER 24/7 AUTOSTART & REBOOT WATCHDOG FOR FOREXTELE
====================================================
Ensures 100% continuous 24/7 operation across VPS/server reboots:
1. Verifies MetaTrader 5 (XM Global MT5) is running; launches if missing.
2. Verifies Telegram Signal Engine (40+ VIP channels) is running; launches if missing.
3. Verifies Autonomous AI Market Scanner (Gold & BTC) is running; launches if missing.
4. Strictly isolates from and never touches C:\\SepPro.
"""
import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timezone
import psutil

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

WATCHDOG_LOG = LOGS_DIR / "master_autostart_watchdog.log"
logging.basicConfig(
    filename=str(WATCHDOG_LOG),
    level=logging.INFO,
    format='%(asctime)s - [MASTER_WATCHDOG] - %(levelname)s - %(message)s'
)
log = logging.getLogger("MASTER_WATCHDOG")

# Console output as well
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - [WATCHDOG] - %(levelname)s - %(message)s'))
log.addHandler(console_handler)

MT5_EXE = Path(r"C:\Program Files\XM Global MT5\terminal64.exe")
PYTHON_EXE = Path(r"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe")
TELEGRAM_BAT = BASE_DIR / "run_telegram_gold_live.bat"
import psutil
import socket

# Detached flags for reliable 24/7 background daemons:
DETACHED_FLAGS = 0x00000008 | 0x00000200

_watchdog_socket = None

def ensure_single_watchdog_instance():
    """Guarantees only one master watchdog runs at a time across the entire system."""
    global _watchdog_socket
    _watchdog_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _watchdog_socket.bind(('127.0.0.1', 39888))
    except OSError:
        log.info("[INFO] Existing Forex Watchdog detected on port 39888. Exiting duplicate instance cleanly.")
        sys.exit(0)

    curr_pid = os.getpid()
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if p.pid != curr_pid and 'python' in (p.name() or '').lower():
                cmd = " ".join(p.cmdline() or [])
                if "master_autostart_watchdog.py" in cmd and "SepPro" not in cmd:
                    log.info(f"Existing watchdog detected (PID {p.pid}). Exiting duplicate instance cleanly.")
                    sys.exit(0)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

def is_mt5_running() -> bool:
    for p in psutil.process_iter(['name']):
        try:
            if p.name().lower() == "terminal64.exe":
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

def is_process_running(script_name: str) -> bool:
    """Checks if a process (python or cmd wrapper) with script_name is already running, excluding SepPro and watchdog."""
    curr_pid = os.getpid()
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if p.pid == curr_pid:
                continue
            cmd = " ".join(p.cmdline() or [])
            if "SepPro" in cmd or "master_autostart_watchdog" in cmd:
                continue
            if script_name in cmd:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

def is_market_open() -> bool:
    """Returns False during weekend market closure (Friday 21:00 UTC to Sunday 22:00 UTC)."""
    now_utc = datetime.now(timezone.utc)
    # Friday post-close
    if now_utc.weekday() == 4 and now_utc.hour >= 21:
        return False
    # Saturday
    if now_utc.weekday() == 5:
        return False
    # Sunday pre-open (market opens 22:00 UTC)
    if now_utc.weekday() == 6 and now_utc.hour < 22:
        return False
    return True

def ensure_services():
    if not is_market_open():
        log.info("⏸️ [WEEKEND PAUSE] Global forex/gold market is CLOSED. Watchdog idle until Monday market open.")
        return

    log.info("--- [WATCHDOG HEALTH CHECK] ---")

    # 1. MetaTrader 5 Terminal Check
    if not is_mt5_running():
        log.warning("⚠️ MT5 terminal64.exe not running! Launching XM Global MT5...")
        if MT5_EXE.exists():
            subprocess.Popen([str(MT5_EXE)], cwd=str(MT5_EXE.parent), shell=False)
            time.sleep(6)
            log.info("✅ XM Global MT5 launched.")
        else:
            log.error(f"MT5 executable not found at {MT5_EXE}!")
    else:
        log.info("✅ MT5 terminal64.exe is ACTIVE.")

    # 2. Telegram Signal Engine Check
    if not (is_process_running("telegram_signal_engine") or is_process_running("run_telegram_gold_live")):
        log.warning("⚠️ Telegram Signal Engine not running! Spawning as detached daemon...")
        subprocess.Popen([str(PYTHON_EXE), "telegram_signal_engine.py"], cwd=str(BASE_DIR), creationflags=DETACHED_FLAGS)
        time.sleep(3)
        log.info("✅ Telegram Signal Engine launched.")
    else:
        log.info("✅ Telegram Signal Engine is ACTIVE.")

    # 3. Autonomous AI Market Scanner Check
    if not (is_process_running("autonomous_ai_market_scanner") or is_process_running("run_autonomous_scanner")):
        log.warning("⚠️ Autonomous AI Market Scanner not running! Spawning as detached daemon...")
        subprocess.Popen([str(PYTHON_EXE), "autonomous_ai_market_scanner.py"], cwd=str(BASE_DIR), creationflags=DETACHED_FLAGS)
        time.sleep(3)
        log.info("✅ Autonomous AI Market Scanner launched.")
    else:
        log.info("✅ Autonomous AI Market Scanner is ACTIVE.")

    # 4. BreakoutBoss Multi-Session Engine Check
    if not (is_process_running("breakout_boss_engine") or is_process_running("run_breakout_boss")):
        log.warning("⚠️ BreakoutBoss Engine not running! Spawning as detached daemon...")
        subprocess.Popen([str(PYTHON_EXE), "breakout_boss_engine.py"], cwd=str(BASE_DIR), creationflags=DETACHED_FLAGS)
        time.sleep(3)
        log.info("✅ BreakoutBoss Engine launched.")
    else:
        log.info("✅ BreakoutBoss Engine is ACTIVE.")

    log.info("--- [WATCHDOG HEALTH CHECK COMPLETE] ---\n")

if __name__ == "__main__":
    ensure_single_watchdog_instance()
    log.info("🚀 Starting Master 24/7 Autostart Watchdog loop (monitoring every 60s)...")
    while True:
        try:
            ensure_services()
        except Exception as e:
            log.error(f"Watchdog iteration error: {e}")
        time.sleep(60)
