import subprocess
import sys
import threading
import os
import time
from datetime import datetime
import json
import logging
import MetaTrader5 as mt5

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
CONFIG_PATH = os.path.join(BASE_DIR, "mt5_config.json")
STATUS_FILE = os.path.join(BASE_DIR, "thread_status.json")
ALERTS_FILE = os.path.join(BASE_DIR, "alerts.json")

def init_mt5_silent():
    if not mt5.initialize():
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH) as f:
                    cfg = json.load(f)
                mt5.initialize(login=cfg.get("login"), server=cfg.get("server"), password=cfg.get("password"))
        except:
            pass
    return mt5.terminal_info() is not None

class ForexConsoleMaster:
    def __init__(self):
        self.processes = {}
        self.running = True
        self.service_scripts = {
            "AI_STRATEGY_ENGINE (Multi-TF & Crypto)": ("live_strategy_executor.py", "python"),
            "WEBSOCKET_DATA_BRIDGE (Port 8888)": ("dashboard_websocket.py", "python"),
            "TELEGRAM_SIGNAL_ENGINE": ("telegram_signal_engine.py", "python"),
            "SWARM_POSITION_MANAGER": ("swarm_position_manager.py", "python"),
        }
        
    def start_service_quiet(self, name, target, proc_type):
        if proc_type == "python":
            full_path = os.path.join(BASE_DIR, target)
            if not os.path.exists(full_path):
                return
            env = os.environ.copy()
            env["PYTHONPATH"] = r"c:\anlyzeforex\forextele\lib\site-packages"
            p = subprocess.Popen(
                [sys.executable, "-u", target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                cwd=BASE_DIR
            )
            self.processes[name] = p
        elif proc_type == "npm":
            ui_dir = os.path.join(BASE_DIR, "dashboard_ui")
            if os.path.exists(ui_dir):
                p = subprocess.Popen(
                    "npm run dev -- --host 0.0.0.0 --port 5555",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=ui_dir
                )
                self.processes[name] = p

    def read_json_safe(self, path, default_val):
        if not os.path.exists(path):
            return default_val
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return json.load(f)
        except:
            return default_val

    def render_console(self):
        if sys.stdout.isatty():
            os.system("cls" if os.name == "nt" else "clear")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print("==================================================================================")
        print("        FOREX AI SWARM OS - LIVE INTERACTIVE TERMINAL (EXCLUSIVE TO FOREX)        ")
        print("==================================================================================")
        print(f" Timestamp: {now_str}  |  Dashboard UI (On-Demand): http://localhost:5555")
        print("==================================================================================\n")
        
        # 1. MT5 Account Pulse
        mt5_online = init_mt5_silent()
        if mt5_online:
            acc = mt5.account_info()
            if acc:
                print("--- [ MT5 LIVE ACCOUNT PULSE ] ---")
                print(f" Account Login : {acc.login:<12} | Server      : {acc.server}")
                print(f" Balance       : ${acc.balance:<11.2f} | Equity      : ${acc.equity:<11.2f}")
                print(f" Free Margin   : ${acc.margin_free:<11.2f} | Floating P&L: ${acc.profit:<11.2f}\n")
            else:
                print("--- [ MT5 LIVE ACCOUNT PULSE ] --- (Connected, fetching account stats...)\n")
        else:
            print("--- [ MT5 LIVE ACCOUNT PULSE ] --- (Attempting Terminal Re-connection...)\n")

        # 2. System Service Heartbeats
        print("--- [ SWARM CORE SERVICES & TELEGRAM STATUS ] ---")
        for s_name, p in self.processes.items():
            state = "ONLINE (Running)" if p.poll() is None else f"OFFLINE (Code {p.poll()})"
            print(f"  * {s_name:<42} : {state}")
        print()

        # 3. Live Symbol Scanning & Weekend Statuses
        status_dict = self.read_json_safe(STATUS_FILE, {})
        print("--- [ MULTI-TIMEFRAME STRATEGY SCANNING TICKER ] ---")
        if status_dict:
            # Display special managers first
            trail = status_dict.get("TRAILING_ENGINE", "Standby")
            pnl_tk = status_dict.get("PNL_TRACKER", "Standby")
            print(f"  [MANAGERS] Trailing Stop: {trail:<24} | PnL Tracker: {pnl_tk}")
            print(f"  {'-'*76}")
            
            # Display Symbols in columns or clean table
            target_symbols = ["GOLD", "SILVER", "GBPJPY", "USDCHF", "AUDUSD", "USDJPY", "GBPUSD", "BTCUSD", "ETHUSD", "EURUSD"]
            for sym in target_symbols:
                st = status_dict.get(sym, "Initialized / Awaiting first Tick...")
                # Format tag for visual clarity in ascii
                tag = "ACTIVE (24/7 CRYPTO)" if sym in ("BTCUSD", "ETHUSD") else "TRADITIONAL ASSET"
                print(f"  * [{sym:<6}] ({tag:<20}) -> {st}")
        else:
            print("  Awaiting Strategy Engine initialization dump...")
        print()

        # 4. Open Positions Showcase
        if mt5_online:
            positions = mt5.positions_get()
            print("--- [ LIVE ACTIVE POSITIONS ] ---")
            if positions and len(positions) > 0:
                print(f" {'Symbol':<8} {'Type':<6} {'Volume':<8} {'Open Price':<12} {'Current':<12} {'Floating P&L ($)':<15}")
                print(f" {'-'*65}")
                for pos in positions:
                    ptype = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                    print(f" {pos.symbol:<8} {ptype:<6} {pos.volume:<8} {pos.price_open:<12.5f} {pos.price_current:<12.5f} ${pos.profit:<12.2f}")
            else:
                print("  No active positions at this second. AI models actively surveying liquidity...")
            print()

        # 5. Recent System Notifications & Alerts
        alerts = self.read_json_safe(ALERTS_FILE, [])
        if alerts and len(alerts) > 0:
            print("--- [ RECENT AI ENGINE ALERTS ] ---")
            for a in alerts[-3:]:
                ts = a.get("timestamp", "")
                src = a.get("source", "Engine")
                msg = a.get("message", "")
                print(f"  [{ts}] [{src}]: {msg}")
            print()

        print("==================================================================================")
        print("  NOTE: Open http://localhost:5555 in your browser on-demand for graphical UI.    ")
        print("  Press Ctrl+C at any time in this window to gracefully shut down the Forex Swarm.  ")
        print("==================================================================================")

    def run_master_console(self):
        # 1. Launch backend python services
        for s_name, (script_target, ptype) in self.service_scripts.items():
            self.start_service_quiet(s_name, script_target, ptype)
            
        # 2. Launch React UI frontend on port 5555
        self.start_service_quiet("REACT_DASHBOARD_UI (Port 5555)", "", "npm")
        
        # 3. Enter real-time rendering loop
        try:
            while self.running:
                self.render_console()
                time.sleep(3) # Refresh every 3 seconds
        except KeyboardInterrupt:
            print("\n[INFO]: Shutdown command detected (Ctrl+C). Terminating Forex Swarm...")
            self.running = False
            for s_name, p in self.processes.items():
                try:
                    p.terminate()
                except:
                    pass
            print("[INFO]: All Forex AI processes stopped. Goodbye!")

if __name__ == "__main__":
    master = ForexConsoleMaster()
    master.run_master_console()
