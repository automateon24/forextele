"""
========================================================================================
FOREXTELE 24/7 AUTONOMOUS RESILIENT MASTER WATCHDOG
Monitors aio_live_trading_engine.py, auto-restarts on crashes, and survives VPS/PC reboots
CRITICAL RULE: Strictly touches only ForexTele processes. NEVER touches SepPro!
========================================================================================
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

WATCHDOG_LOG = LOGS_DIR / "master_watchdog.log"
logging.basicConfig(
    filename=str(WATCHDOG_LOG),
    level=logging.INFO,
    format="%(asctime)s - [WATCHDOG] - %(levelname)s - %(message)s"
)
log = logging.getLogger("WATCHDOG")

console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s - [WATCHDOG] - %(levelname)s - %(message)s"))
log.addHandler(console)

PYTHON_EXE = sys.executable
ENGINE_SCRIPT = BASE_DIR / "aio_live_trading_engine.py"

def kill_stale_forextele_processes():
    current_pid = os.getpid()
    log.info("🔍 Scanning for stale ForexTele processes to clean up...")
    killed = 0
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if p.info['pid'] == current_pid:
                continue
            cmd = ' '.join(p.info['cmdline'] or []).lower()
            
            # STRICT SAFETY SHIELD: NEVER TOUCH SEPPRO
            if "seppro" in cmd:
                continue

            if 'python' in p.info['name'].lower():
                if ('aio_live_trading_engine' in cmd or 
                    'master_autostart_watchdog' in cmd or 
                    'master_runner.py' in cmd):
                    log.info(f"   -> Killing stale ForexTele process PID {p.info['pid']}: {cmd[:80]}")
                    p.terminate()
                    try:
                        p.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        p.kill()
                    killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    log.info(f"✅ Stale process cleanup complete. ({killed} ForexTele processes terminated; SepPro untouched)")

def notify_telegram(text: str):
    try:
        from telegram_notifier import send_msg
        send_msg(text)
    except Exception as e:
        log.warning(f"Telegram notice error: {e}")

def run_watchdog():
    log.info("====================================================================")
    log.info("🛡️ FOREXTELE AUTONOMOUS RESILIENT 24/7 MASTER WATCHDOG INITIATED")
    log.info("   Target Engine: aio_live_trading_engine.py")
    log.info("   Weekend Mode: BTCUSD & ETHUSD Active 24/7")
    log.info("   Weekday Mode: GOLD, SILVER, EURUSD, GBPUSD, USDJPY + Crypto")
    log.info("====================================================================")

    kill_stale_forextele_processes()

    # Send boot alert
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    is_weekend = (datetime.now(timezone.utc).weekday() >= 5)
    mode_str = "🌐 24/7 Weekend Crypto (BTCUSD, ETHUSD)" if is_weekend else "🔄 Multi-Asset All-Pairs"
    notify_telegram(
        f"🚀 <b>[FOREXTELE ENGINE LAUNCHED FRESH]</b>\n\n"
        f"<b>Status:</b> Active 24/7 Watchdog Supervised\n"
        f"<b>Active Mode:</b> {mode_str}\n"
        f"<b>Watchdog Host:</b> VPS / Local Machine Auto-Recover Enabled\n"
        f"<i>Time: {now_str}</i>"
    )

    while True:
        log.info(f"🚀 Spawning fresh instance of {ENGINE_SCRIPT.name}...")
        try:
            # Launch child process
            proc = subprocess.Popen(
                [PYTHON_EXE, str(ENGINE_SCRIPT)],
                cwd=str(BASE_DIR),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            log.info(f"✅ Child process started successfully with PID {proc.pid}")

            # Monitor loop
            while True:
                ret = proc.poll()
                if ret is not None:
                    log.warning(f"⚠️ Engine process (PID {proc.pid}) exited unexpectedly with code {ret}!")
                    notify_telegram(
                        f"⚠️ <b>[FOREXTELE WATCHDOG NOTICE]</b>\n\n"
                        f"Engine exited with code {ret}.\n"
                        f"🔄 <b>Auto-Restarting freshly in 5 seconds...</b>"
                    )
                    break
                time.sleep(10)

        except Exception as e:
            log.error(f"Error managing child process: {e}")

        log.info("Waiting 5 seconds before clean restart...")
        time.sleep(5)
        kill_stale_forextele_processes()

if __name__ == "__main__":
    run_watchdog()
