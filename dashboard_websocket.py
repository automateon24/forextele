import asyncio
import websockets
import json
import logging
import MetaTrader5 as mt5
from pathlib import Path
import time
from datetime import datetime
import pytz
import tailer # Make sure this is installed or we use a custom tail logic
import csv
from telegram_signal_engine import FOREX_GOLD_VIPS, CRYPTO_VIPS

BASE_DIR = Path(__file__).parent
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"
AUDIT_CSV_PATH = BASE_DIR / "signals_audit.csv"

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WS_BRIDGE] - %(message)s')

def get_mt5_data():
    """Fetch live data from MT5 for the dashboard"""
    if not mt5.terminal_info():
        # Try to connect
        try:
            with open(MT5_CFG_PATH, "r") as f:
                cfg = json.load(f)
            mt5.initialize(login=int(cfg["login"]), server=cfg["server"], password=cfg["password"])
        except Exception:
            return {"error": "MT5 Disconnected"}

    acc = mt5.account_info()
    positions = mt5.positions_get()
    
    if not acc:
        return {"error": "Account Info Unavailable"}

    # Format positions
    active_positions = []
    if positions:
        for p in positions:
            active_positions.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "open_price": p.price_open,
                "current_price": p.price_current,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "magic": p.magic,
                "comment": p.comment
            })

    from datetime import timedelta
    # Calculate Today's Realized PnL and Win Rate
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    history_deals = mt5.history_deals_get(yesterday, now)
    
    tele_pnl = 0.0
    tele_wins = 0
    tele_losses = 0
    
    strat_pnl = 0.0
    strat_wins = 0
    strat_losses = 0
    
    if history_deals:
        for deal in history_deals:
            if deal.entry == mt5.DEAL_ENTRY_OUT: # Only closed positions
                if deal.magic == 999999:
                    tele_pnl += deal.profit
                    if deal.profit > 0: tele_wins += 1
                    elif deal.profit < 0: tele_losses += 1
                else:
                    strat_pnl += deal.profit
                    if deal.profit > 0: strat_wins += 1
                    elif deal.profit < 0: strat_losses += 1
                    
    tele_win_rate = (tele_wins / (tele_wins + tele_losses) * 100) if (tele_wins + tele_losses) > 0 else 0.0
    strat_win_rate = (strat_wins / (strat_wins + strat_losses) * 100) if (strat_wins + strat_losses) > 0 else 0.0
    
    # Read Thread Status
    thread_status = {}
    try:
        with open(BASE_DIR / "thread_status.json", "r") as f:
            thread_status = json.load(f)
    except:
        pass

    # Fetch live spreads and trends for Tickers
    target_symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "GOLD", "SILVER", "BTCUSD", "ETHUSD"]
    tickers_data = []
    for sym in target_symbols:
        tick = mt5.symbol_info_tick(sym)
        info = mt5.symbol_info(sym)
        if tick and info:
            spread = (tick.ask - tick.bid) / info.point
            price = tick.bid
            status = thread_status.get(sym, "CONSOLIDATION").upper()
            spread_val = round(spread, 1)
            swap = info.swap_long if hasattr(info, 'swap_long') else 0
        else:
            price = 0
            status = "MARKET CLOSED"
            spread_val = 0
            swap = 0
            
        tickers_data.append({
            "symbol": sym,
            "price": price,
            "spread": spread_val,
            "swap": round(swap, 2),
            "trend": "NORMAL",
            "status": status
        })

    return {
        "account": {
            "balance": acc.balance,
            "equity": acc.equity,
            "margin": acc.margin,
            "margin_free": acc.margin_free,
            "margin_level": acc.margin_level
        },
        "positions": active_positions,
        "timestamp": time.time(),
        "today_pnl": strat_pnl + tele_pnl,
        "tele_pnl": tele_pnl,
        "strat_pnl": strat_pnl,
        "tele_wins": tele_wins,
        "tele_losses": tele_losses,
        "tele_win_rate": round(tele_win_rate, 1),
        "strat_wins": strat_wins,
        "strat_losses": strat_losses,
        "strat_win_rate": round(strat_win_rate, 1),
        "tickers": tickers_data
    }

def get_latest_ai_logs():
    """Tails the last 15 lines of the Swarm Master log to simulate live terminal feed"""
    log_file = BASE_DIR / "master_swarm_runner.log"
    logs = []
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                logs = [l.strip() for l in lines[-15:]]
        except:
            pass
    return logs

def get_signal_audit():
    """Reads the last 50 entries from signals_audit.csv"""
    audit = []
    if AUDIT_CSV_PATH.exists():
        try:
            with open(AUDIT_CSV_PATH, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                audit = list(reader)[-50:] # Get last 50 rows
                audit.reverse() # Newest first
        except Exception as e:
            log.error(f"Error reading audit csv: {e}")
    return audit

async def broadcast_telemetry(websocket):
    """Continuously push JSON to the React Frontend every second"""
    log.info("React Dashboard Client Connected.")
    try:
        while True:
            mt5_data = get_mt5_data()
            logs = get_latest_ai_logs()
            audit = get_signal_audit()
            
            ist = pytz.timezone('Asia/Kolkata')
            
            payload = {
                "mt5": mt5_data,
                "ai_logs": logs,
                "signal_audit": audit,
                "all_channels": FOREX_GOLD_VIPS + CRYPTO_VIPS,
                "server_time": datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST"),
                "telegram_status": "🟢 TELEGRAM LIVE",
                "strategies_scanning": 8,
                "active_channels": ["SURESHOT GOLD VIP", "FOREX SIGNALS PRO", "CRYPTO WHALES"]
            }
            
            await websocket.send(json.dumps(payload))
            await asyncio.sleep(1.0) # 1 second refresh rate
            
    except websockets.exceptions.ConnectionClosed:
        log.info("React Dashboard Client Disconnected.")

async def handle_client(websocket):
    """Handle both sending telemetry and receiving commands"""
    log.info("React Dashboard Client Connected.")
    
    # Run the sender and receiver concurrently
    sender_task = asyncio.create_task(broadcast_telemetry(websocket))
    
    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")
            
            if action == "KILL_SWITCH":
                log.warning("🚨 KILL SWITCH ACTIVATED: CLOSING ALL POSITIONS 🚨")
                positions = mt5.positions_get()
                if positions:
                    for pos in positions:
                        tick = mt5.symbol_info_tick(pos.symbol)
                        # pos.type is 0 (BUY) or 1 (SELL)
                        is_buy = (pos.type == 0 or pos.type == mt5.ORDER_TYPE_BUY)
                        price = tick.bid if is_buy else tick.ask
                        type_close = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
                        
                        req = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "symbol": pos.symbol,
                            "volume": pos.volume,
                            "type": type_close,
                            "position": pos.ticket,
                            "price": price,
                            "magic": pos.magic,
                            "comment": "KILL_SWITCH",
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": mt5.ORDER_FILLING_IOC,
                        }
                        result = mt5.order_send(req)
                        log.info(f"Kill Switch Close Result for {pos.ticket}: {result}")
                
            elif action == "TEST_BUY_GOLD":
                log.info("TEST COMMAND: Executing 0.01 BUY on XAUUSD")
                tick = mt5.symbol_info_tick("XAUUSD")
                if tick:
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": "XAUUSD",
                        "volume": 0.01,
                        "type": mt5.ORDER_TYPE_BUY,
                        "price": tick.ask,
                        "magic": 111111,
                        "comment": "TEST_ORDER",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    result = mt5.order_send(req)
                    log.info(f"Test Buy Result: {result}")
                
            elif action == "TEST_SELL_GOLD":
                log.info("TEST COMMAND: Executing 0.01 SELL on XAUUSD")
                tick = mt5.symbol_info_tick("XAUUSD")
                if tick:
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": "XAUUSD",
                        "volume": 0.01,
                        "type": mt5.ORDER_TYPE_SELL,
                        "price": tick.bid,
                        "magic": 111111,
                        "comment": "TEST_ORDER",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    result = mt5.order_send(req)
                    log.info(f"Test Sell Result: {result}")
                
    except websockets.exceptions.ConnectionClosed:
        sender_task.cancel()
        log.info("React Dashboard Client Disconnected.")

async def main():
    log.info("Booting WebSocket Bridge on ws://localhost:8888...")
    async with websockets.serve(handle_client, "localhost", 8888):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
