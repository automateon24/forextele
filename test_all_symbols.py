import json
import time
import logging
from pathlib import Path
import MetaTrader5 as mt5

BASE_DIR = Path(__file__).parent
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"
MT5_CFG = json.loads(MT5_CFG_PATH.read_text(encoding="utf-8"))

logging.basicConfig(level=logging.INFO, format="%(message)s")

# Define target instruments to look for
TARGET_FOREX = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD", # Majors
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD", "EURCHF" # Minors
]
TARGET_METALS = ["GOLD", "SILVER", "XAUUSD", "XAGUSD"]
TARGET_CRYPTO = ["BTCUSD", "ETHUSD", "BTC", "ETH"]

def get_best_match(available_symbols, target_list):
    """Find the exact or closest matching symbol on the broker"""
    matched = []
    avail_names = [s.name for s in available_symbols]
    for target in target_list:
        # Exact match
        if target in avail_names:
            matched.append(target)
            continue
        # Substring match (e.g. BTCUSDm)
        for name in avail_names:
            if target in name.upper() and name not in matched:
                matched.append(name)
                break
    return matched

def place_order(symbol: str, action: str, volume: float = 0.01):
    req_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).ask if action == "BUY" else mt5.symbol_info_tick(symbol).bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": req_type,
        "price": price,
        "deviation": 20,
        "magic": 555555,
        "comment": "MassTester",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"❌ {action} {symbol} failed: {result.retcode} - {result.comment}")
        return None
    logging.info(f"✅ {action} {symbol} success: Ticket {result.order} @ {result.price}")
    return result.order

def close_position(ticket: int, symbol: str, action: str, volume: float = 0.01):
    close_type = mt5.ORDER_TYPE_SELL if action == "BUY" else mt5.ORDER_TYPE_BUY
    price = mt5.symbol_info_tick(symbol).bid if action == "BUY" else mt5.symbol_info_tick(symbol).ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": ticket,
        "symbol": symbol,
        "volume": volume,
        "type": close_type,
        "price": price,
        "deviation": 20,
        "magic": 555555,
        "comment": "CloseMassTester",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"❌ Failed to close {symbol} (Ticket {ticket}): {result.comment}")
        return False
    logging.info(f"✅ Closed {symbol} (Ticket {ticket})")
    return True

def run_mass_test():
    if not mt5.initialize(login=MT5_CFG["login"], server=MT5_CFG["server"], password=MT5_CFG["password"]):
        logging.error(f"MT5 init failed: {mt5.last_error()}")
        return

    logging.info("Connected to MT5. Fetching symbols...")
    all_symbols = mt5.symbols_get()
    
    forex_symbols = get_best_match(all_symbols, TARGET_FOREX)
    metal_symbols = get_best_match(all_symbols, TARGET_METALS)
    crypto_symbols = get_best_match(all_symbols, TARGET_CRYPTO)
    
    test_symbols = list(set(forex_symbols + metal_symbols + crypto_symbols))
    logging.info(f"Found {len(test_symbols)} instruments to test: {test_symbols}")
    
    open_tickets = []
    
    for sym in test_symbols:
        if not mt5.symbol_select(sym, True):
            logging.warning(f"Could not select {sym} in Market Watch.")
            continue
            
        sym_info = mt5.symbol_info(sym)
        if not sym_info or not sym_info.visible:
            logging.warning(f"{sym} not visible.")
            continue
            
        # Ensure we respect minimum volume
        vol = max(0.01, sym_info.volume_min)
        
        logging.info(f"\n--- Testing {sym} (Volume: {vol}) ---")
        buy_ticket = place_order(sym, "BUY", vol)
        if buy_ticket:
            open_tickets.append({"ticket": buy_ticket, "symbol": sym, "action": "BUY", "volume": vol})
            
        time.sleep(0.5)
        
        sell_ticket = place_order(sym, "SELL", vol)
        if sell_ticket:
            open_tickets.append({"ticket": sell_ticket, "symbol": sym, "action": "SELL", "volume": vol})
            
    logging.info(f"\n--- Waiting 60 seconds before closing {len(open_tickets)} positions... ---")
    time.sleep(60)
    
    logging.info("\n--- Closing positions... ---")
    for pos in open_tickets:
        close_position(pos["ticket"], pos["symbol"], pos["action"], pos["volume"])
        time.sleep(0.5)
        
    mt5.shutdown()
    logging.info("Mass test complete!")

if __name__ == "__main__":
    run_mass_test()
