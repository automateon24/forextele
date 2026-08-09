import json
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [RESET] - %(message)s')
log = logging.getLogger(__name__)

BASE_DIR = r"c:\anlyzeforex\forextele"

def reset_json(filename, default_content):
    path = os.path.join(BASE_DIR, filename)
    try:
        with open(path, "w") as f:
            json.dump(default_content, f, indent=4)
        log.info(f"✅ Reset: {filename}")
    except Exception as e:
        log.error(f"Failed to reset {filename}: {e}")

def wipe_logs():
    log_files = [
        "live_strategy_executor.log",
        "live_order_executor.log",
        "mt5_orders.log",
        "master_swarm_runner.log"
    ]
    for log_file in log_files:
        path = os.path.join(BASE_DIR, log_file)
        if os.path.exists(path):
            try:
                open(path, 'w').close()
                log.info(f"✅ Cleared Log: {log_file}")
            except:
                pass

def main():
    log.info("Starting complete Dashboard & Engine metric reset...")
    
    # 1. Reset PnL and Performance Metrics
    reset_json("strategy_pnl_today.json", {"realized_pnl": 0.0, "unrealized_pnl": 0.0, "win_rate": 0.0, "total_trades": 0, "wins": 0, "losses": 0, "history": []})
    reset_json("positions_status.json", {})
    reset_json("live_health_metrics.json", {"history": []})
    reset_json("alerts.json", [])
    
    # 2. Reset Thread/Engine Statuses
    reset_json("thread_status.json", {})
    reset_json("telegram_status.json", {"last_update": "", "active_channels": 0, "signals_today": 0})
    
    # 3. Reset Parsed Telegram Signals
    reset_json("telegram_parsed_15days.json", [])
    reset_json("telegram_parsed_90days.json", [])
    
    # 4. Clear bloated logs
    wipe_logs()
    
    log.info("Reset complete. The V2 Engine will now start with a completely fresh slate.")

if __name__ == "__main__":
    main()
