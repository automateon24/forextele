import subprocess
import sys
import threading
import os
import time
from datetime import datetime
import json
import logging

# Ensure we are running in the correct directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [SWARM_MASTER] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("master_swarm_runner.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

class SwarmThreadManager:
    def __init__(self):
        self.processes = {}
        # We will map logical names to the actual python scripts
        self.services = {
            "TELEGRAM_LISTENER": "telegram_signal_engine.py", # Using the brand new Swarm engine
            "STRATEGY_ENGINE": "live_strategy_executor.py",
            "WEBSOCKET_BRIDGE": "dashboard_websocket.py",  # To be built in Phase 4
            "POSITION_MANAGER": "swarm_position_manager.py", # Trail Boss Intelligence
        }
        self.running = True
        
    def stream_output(self, process, name):
        """Continuously read output from a subprocess and log it."""
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    log.info(f"[{name}] {line.strip()}")
        except ValueError:
            pass # Process closed

    def start_service(self, name, script_name):
        """Launch a specific python script as an isolated subprocess."""
        if not os.path.exists(os.path.join(BASE_DIR, script_name)):
            log.warning(f"Script {script_name} not found yet (Skipping for now).")
            return
            
        log.info(f"Starting isolated thread for {name} ({script_name})...")
        
        env = os.environ.copy()
        env["PYTHONPATH"] = r"c:\anlyzeforex\forextele\lib\site-packages"
        
        p = subprocess.Popen(
            [sys.executable, "-u", script_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )
        self.processes[name] = p
        
        # Start logging thread
        t = threading.Thread(target=self.stream_output, args=(p, name), daemon=True)
        t.start()

    def health_monitor(self):
        """Thread 2: Health Monitor - Checks system pulse continuously."""
        log.info("Health Monitor Online. Watching Swarm components...")
        while self.running:
            for name, p in list(self.processes.items()):
                if p.poll() is not None: # Process has died
                    log.error(f"CRITICAL: {name} has crashed! Code: {p.returncode}")
                    # Attempt Restart
                    log.info(f"Attempting to restart {name}...")
                    self.start_service(name, self.services.get(name))
            time.sleep(10)

    def eod_github_scheduler(self):
        """Thread 4: End-of-Day GitHub Backup Scheduler."""
        log.info("EOD Backup Scheduler Online.")
        while self.running:
            now = datetime.now()
            # Run daily at 23:55
            if now.hour == 23 and now.minute == 55:
                log.info("Triggering EOD GitHub Backup...")
                backup_script = "eod_github_sync.py"
                if os.path.exists(os.path.join(BASE_DIR, backup_script)):
                    subprocess.run([sys.executable, backup_script])
                time.sleep(60) # Sleep for a minute to avoid re-triggering
            time.sleep(30)

    def launch_swarm(self):
        log.info("=======================================")
        log.info(" INITIATING FOREX AI SWARM SYSTEM ")
        log.info("=======================================")
        
        # 1. Launch Services
        for name, script in self.services.items():
            self.start_service(name, script)
            
        # 2. Launch Health Monitor
        threading.Thread(target=self.health_monitor, daemon=True).start()
        
        # 3. Launch EOD Backup Scheduler
        threading.Thread(target=self.eod_github_scheduler, daemon=True).start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("Manual kill switch activated. Terminating Swarm...")
            self.running = False
            for name, p in self.processes.items():
                p.terminate()
            log.info("Swarm offline.")

if __name__ == "__main__":
    manager = SwarmThreadManager()
    manager.launch_swarm()
