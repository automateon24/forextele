import zmq
import time
import json
import logging
import MetaTrader5 as mt5
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "mt5_config.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [MARKET_DATA] - %(levelname)s - %(message)s')

def init_mt5():
    if not mt5.initialize():
        login = os.environ.get("MT5_LOGIN")
        server = os.environ.get("MT5_SERVER")
        password = os.environ.get("MT5_PASSWORD")

        if not (login and server and password) and os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            login = cfg.get('login')
            server = cfg.get('server')
            password = cfg.get('password')

        if login and server and password:
            mt5.initialize(login=int(login), server=server, password=password)
    return mt5.terminal_info() is not None

def main():
    if not init_mt5():
        logging.error("Failed to connect to MT5. Market Data Service halting.")
        return

    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://127.0.0.1:5555")
    logging.info("Market Data Service bound to tcp://127.0.0.1:5555")

    target_symbols = ["GOLD", "SILVER", "GBPJPY", "USDCHF", "AUDUSD", "USDJPY", "GBPUSD", "BTCUSD", "ETHUSD", "EURUSD"]
    symbols = [s for s in target_symbols if mt5.symbol_info(s) is not None]

    logging.info(f"Publishing data for symbols: {symbols}")

    while True:
        try:
            for symbol in symbols:
                # Fetch recent M15 candles to act as the "closed bar" data feed
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 52)
                if rates is not None and len(rates) > 1:
                    # The second to last is the most recently fully closed candle. We send the last 50 closed.
                    closed_bars = rates[-51:-1]
                    
                    history = []
                    for b in closed_bars:
                        history.append({
                            "time": int(b['time']),
                            "open": float(b['open']),
                            "high": float(b['high']),
                            "low": float(b['low']),
                            "close": float(b['close']),
                            "tick_volume": int(b['tick_volume'])
                        })

                    message = {
                        "event": "BarClosed",
                        "symbol": symbol,
                        "timeframe": "M15",
                        "history": history
                    }
                    socket.send_string(f"MARKET_DATA {json.dumps(message)}")
            
            time.sleep(5)  # Throttle polling to 5s
        except KeyboardInterrupt:
            logging.info("Shutting down Market Data Service.")
            break
        except Exception as e:
            logging.error(f"Error in Market Data loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
