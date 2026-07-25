import MetaTrader5 as mt5
import pandas as pd
import time
import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [HEALTH_MONITOR] - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"
HEALTH_LOG = BASE_DIR / "live_health_metrics.json"

class SwarmHealthMonitor:
    def __init__(self):
        self.connect()
        self.active_trades = {}
        self.historical_performance = []

    def connect(self):
        if not mt5.initialize():
            try:
                with open(MT5_CFG_PATH, "r") as f:
                    cfg = json.load(f)
                mt5.initialize(login=int(cfg["login"]), server=cfg["server"], password=cfg["password"])
            except Exception as e:
                log.error(f"MT5 Init Error: {e}")

    def scan_active_positions(self):
        positions = mt5.positions_get()
        if positions is None:
            log.warning("Failed to retrieve positions.")
            return

        current_tickets = []
        for pos in positions:
            ticket = pos.ticket
            current_tickets.append(ticket)
            
            if ticket not in self.active_trades:
                # New trade detected
                log.info(f"🚨 LIVE TRADE DETECTED: {pos.symbol} - Type: {pos.type} - Entry: {pos.price_open}")
                self.active_trades[ticket] = {
                    "symbol": pos.symbol,
                    "entry_price": pos.price_open,
                    "sl": pos.sl,
                    "tp": pos.tp,
                    "volume": pos.volume,
                    "open_time": datetime.utcnow().isoformat(),
                    "comment": pos.comment
                }
                
        # Check for closed trades (drift monitoring)
        closed_tickets = [t for t in self.active_trades.keys() if t not in current_tickets]
        for ticket in closed_tickets:
            self.process_closed_trade(ticket)

    def process_closed_trade(self, ticket):
        trade = self.active_trades.pop(ticket)
        
        # In a real environment, you'd fetch history deals here using mt5.history_deals_get
        # For health monitoring, we just log the closure event
        log.info(f"✅ TRADE CLOSED: {trade['symbol']} (Strategy: {trade['comment']})")
        
        trade['close_time'] = datetime.utcnow().isoformat()
        self.historical_performance.append(trade)
        self.save_health_metrics()

    def save_health_metrics(self):
        try:
            with open(HEALTH_LOG, "w") as f:
                json.dump({"history": self.historical_performance}, f, indent=4)
        except Exception as e:
            log.error(f"Failed to save health metrics: {e}")

    def run(self):
        log.info("SWARM HEALTH MONITOR ONLINE. Tracking real-time execution drift...")
        while True:
            self.scan_active_positions()
            time.sleep(10) # Poll every 10 seconds

if __name__ == "__main__":
    monitor = SwarmHealthMonitor()
    monitor.run()
