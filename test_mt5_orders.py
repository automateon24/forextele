import json
import logging
from pathlib import Path
import time
import MetaTrader5 as mt5

BASE_DIR = Path(__file__).parent
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"
MT5_CFG = json.loads(MT5_CFG_PATH.read_text(encoding="utf-8"))

logging.basicConfig(level=logging.INFO, format="%(message)s")

def test_orders():
    # Initialize MT5
    if not mt5.initialize(login=MT5_CFG["login"], server=MT5_CFG["server"], password=MT5_CFG["password"]):
        logging.error(f"MT5 init failed: {mt5.last_error()}")
        return

    logging.info(f"Connected to MT5, version: {mt5.version()}")
    
    symbol = "GOLD"
    logging.info(f"Will try trading on symbol: {symbol}")
    
    # Ensure symbol is visible
    if not mt5.symbol_select(symbol, True):
        logging.error(f"Failed to select {symbol}")
        mt5.shutdown()
        return
        
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logging.error(f"{symbol} not found")
        mt5.shutdown()
        return

    logging.info(f"Symbol {symbol} found. Ask: {symbol_info.ask}, Bid: {symbol_info.bid}")

    volume = 0.01
    
    # Place BUY order
    buy_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY,
        "price": mt5.symbol_info_tick(symbol).ask,
        "deviation": 20,
        "magic": 123456,
        "comment": "Test Buy",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    logging.info("Sending BUY request...")
    buy_result = mt5.order_send(buy_request)
    
    if buy_result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"BUY order failed: {buy_result.retcode} - {buy_result.comment}")
    else:
        logging.info(f"BUY order successful! Ticket: {buy_result.order}, Price: {buy_result.price}")
        
    time.sleep(2)
    
    # Place SELL order
    sell_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_SELL,
        "price": mt5.symbol_info_tick(symbol).bid,
        "deviation": 20,
        "magic": 123456,
        "comment": "Test Sell",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    logging.info("Sending SELL request...")
    sell_result = mt5.order_send(sell_request)
    
    if sell_result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"SELL order failed: {sell_result.retcode} - {sell_result.comment}")
    else:
        logging.info(f"SELL order successful! Ticket: {sell_result.order}, Price: {sell_result.price}")
        
    mt5.shutdown()

if __name__ == "__main__":
    test_orders()
