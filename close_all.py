import MetaTrader5 as mt5
import json
import time
from pathlib import Path

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
CONFIG_PATH = BASE_DIR / "mt5_config.json"

def main():
    if not mt5.initialize():
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f: cfg = json.load(f)
            mt5.initialize(login=cfg.get('login'), server=cfg.get('server'), password=cfg.get('password'))
            
    if not mt5.terminal_info():
        print("Failed to connect to MT5.")
        return

    positions = mt5.positions_get()
    if not positions:
        print("No open positions found. You are completely flat and ready for Monday!")
        return
        
    print(f"Found {len(positions)} open positions. Closing all...")
    
    for pos in positions:
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            print(f"Skipping {pos.symbol}, market closed or no tick data.")
            continue
            
        action = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if action == mt5.ORDER_TYPE_SELL else tick.ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": action,
            "price": price,
            "deviation": 20,
            "magic": 999999,
            "comment": "Weekend Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"Successfully closed {pos.symbol} (Ticket: {pos.ticket})")
        else:
            print(f"Failed to close {pos.symbol}. Code: {res.retcode if res else 'Unknown'}")
            
    print("All closures processed. The system is locked and ready for Monday.")

if __name__ == "__main__":
    main()
