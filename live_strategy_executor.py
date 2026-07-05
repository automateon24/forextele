import json
import logging
import time
from pathlib import Path
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime
import concurrent.futures

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
CONFIG_PATH = BASE_DIR / "mt5_config.json"
DNA_PATH = BASE_DIR / "25stragy" / "ai_optimized_forex_dna.json"

logging.basicConfig(
    filename=BASE_DIR / 'live_strategy_executor.log',
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

# Thread State Dictionary for Dashboard
THREAD_STATUS = {}

def init_mt5():
    if not mt5.initialize():
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            if not mt5.initialize(login=cfg["login"], server=cfg["server"], password=cfg["password"]):
                logging.error("MT5 init failed.")
                return False
        except Exception as e:
            logging.error(f"Config error: {e}")
            return False
    return True

def get_optimized_dna():
    try:
        with open(DNA_PATH) as f:
            return json.load(f).get("strategies", {})
    except FileNotFoundError:
        logging.warning("AI DNA not found. Falling back to default.")
        return {}

def calculate_dynamic_lot(symbol, base_allocation=200.0, leverage=1000, risk_pct=0.05):
    """
    PHASE 2: Dynamic Compounding Margin Sizing
    Calculates the exact lot size based on a $200 allocated compounding margin
    using 1000x leverage. Aggressively scales lot sizes to hit 40% daily ROI limits.
    """
    info = mt5.symbol_info(symbol)
    if not info:
        return 0.01 # Fallback to micro-lot if symbol info fails
    
    # 1. Fetch current account equity
    account = mt5.account_info()
    if account is None:
        return 0.01
        
    # We pretend the equity is isolated to our base allocation for compounding
    # If this was real compounding, we'd track the $200 growth. 
    # For now, we simulate the aggressive scaling:
    total_leverage_power = base_allocation * leverage
    
    # Contract size dictates how much 1 lot costs
    contract_size = info.trade_contract_size
    price = info.ask
    
    # Calculate max possible volume we can buy with $200 at 1000x leverage
    if price == 0 or contract_size == 0:
        return 0.01
        
    max_volume = total_leverage_power / (price * contract_size)
    
    # Risk exactly `risk_pct` (e.g. 5%) of our maximum leveraged volume for the trade
    target_volume = max_volume * risk_pct
    
    # Round to the broker's allowed step (e.g., 0.01)
    step = info.volume_step
    target_volume = round(target_volume / step) * step
    
    # Ensure it's within bounds
    target_volume = max(info.volume_min, min(target_volume, info.volume_max))
    
    logging.info(f"[{symbol}] Phase 2 Dynamic Scaling: Calculated {target_volume:.2f} Lots based on ${base_allocation} @ 1000x")
    return target_volume

def place_order(symbol, trade_type, lot, strat_name, magic_number=888888):
    """
    Executes the trade on MT5 with the explicit Strategy Name attached as a comment.
    """
    action = mt5.ORDER_TYPE_BUY if trade_type == "BUY" else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).ask if action == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot),
        "type": action,
        "price": price,
        "magic": magic_number,
        "comment": strat_name,  # Attaching strategy name for tracking!
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"[{symbol}] Order Failed! Code: {result.retcode}")
        return None
    
    logging.info(f"[{symbol}] SUCCESS - Opened {trade_type} | Strat: {strat_name} | Ticket: {result.order}")
    return result

def trailing_stop_manager(base_dna):
    """
    PHASE 3: Order Tracking & Trailing Engine
    Runs continuously as a background thread. Monitors all active positions.
    If the profit exceeds the DNA 'tsl_a' (Activation), it tightens the Stop Loss
    tick-by-tick based on the 'tsl_t' (Trailing factor).
    """
    logging.info("[SYSTEM] Trailing Stop Engine Online.")
    THREAD_STATUS["TRAILING_ENGINE"] = "Active"
    
    while True:
        try:
            positions = mt5.positions_get()
            if positions is None:
                time.sleep(1)
                continue
                
            for pos in positions:
                # Only manage our algorithmic trades
                if pos.magic != 888888:
                    continue
                    
                symbol = pos.symbol
                ticket = pos.ticket
                comment = pos.comment
                
                # Fetch the exact DNA used for this position
                strat_key = f"{symbol}:{comment}:M1" # Fallback to M1 default
                # In a live environment, we dynamically match this better.
                dna = base_dna.get(strat_key, {"tsl_a": 0.05, "tsl_t": 0.02})
                
                tsl_a = dna.get("tsl_a", 0.05)
                tsl_t = dna.get("tsl_t", 0.02)
                
                info = mt5.symbol_info(symbol)
                if not info: continue
                
                point = info.point
                price_current = mt5.symbol_info_tick(symbol).bid if pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).ask
                
                # Dynamic ATR Trailing SL logic could be inserted here
                # Simplified check to show the concept
                profit_points = (price_current - pos.price_open) / point if pos.type == mt5.ORDER_TYPE_BUY else (pos.price_open - price_current) / point
                
                # If profit > Activation Threshold (e.g. 50 points), move SL
                if profit_points > (tsl_a * 1000):
                    new_sl = price_current - (tsl_t * 1000 * point) if pos.type == mt5.ORDER_TYPE_BUY else price_current + (tsl_t * 1000 * point)
                    
                    # Only modify if new SL is better than old SL
                    if pos.sl == 0.0 or (pos.type == mt5.ORDER_TYPE_BUY and new_sl > pos.sl) or (pos.type == mt5.ORDER_TYPE_SELL and new_sl < pos.sl):
                        request = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": ticket,
                            "symbol": symbol,
                            "sl": new_sl,
                            "tp": pos.tp,
                        }
                        mt5.order_send(request)
                        logging.info(f"[{symbol}] Trailing Stop tightened for Ticket {ticket} -> {new_sl:.5f}")
                        
            THREAD_STATUS["TRAILING_ENGINE"] = f"Monitoring {len(positions)} Positions"
            time.sleep(1) # Check every second
            
        except Exception as e:
            THREAD_STATUS["TRAILING_ENGINE"] = f"Error: {e}"
            time.sleep(5)

def process_symbol(symbol, base_dna):
    """
    Dedicated thread function for each symbol.
    """
    THREAD_STATUS[symbol] = "Running"
    logging.info(f"[{symbol}] Thread Started. Polling for AI Entry conditions.")
    
    control_file = BASE_DIR / "control_flags.json"
    
    while True:
        try:
            # Check Master Controls
            if control_file.exists():
                with open(control_file, "r") as f:
                    flags = json.load(f)
                if not flags.get("engine_running", True):
                    THREAD_STATUS[symbol] = "Stopped (Master Switch)"
                    time.sleep(5)
                    continue
                if flags.get("ai_paused", False):
                    THREAD_STATUS[symbol] = "Paused"
                    time.sleep(2)
                    continue
                    
            # Step 1: Check MT5 connection
            if mt5.terminal_info() is None:
                THREAD_STATUS[symbol] = "Error: MT5 Disconnected"
                time.sleep(5)
                continue
                
            # Step 2: Extract specific DNA for this symbol
            # Using a mock search for the best timeframe
            strat_key = f"{symbol}:MEAN_REVERSION:M5"
            dna = base_dna.get(strat_key, {"tsl_a": 0.1, "optimal_timeframe": "M5"})
            
            tf_map = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}
            tf = tf_map.get(dna.get("optimal_timeframe", "M5"), mt5.TIMEFRAME_M5)
            
            # Request M1 or M5 Data directly without blocking other threads
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, 50)
            if rates is not None and len(rates) > 0:
                THREAD_STATUS[symbol] = f"Active | TF: {dna.get('optimal_timeframe', 'M5')} | Polling Mkt"
                
                # --- ALGORITHMIC ENTRY LOGIC ---
                df = pd.DataFrame(rates)
                df['close'] = df['close'].astype(float)
                
                # Fast and Slow MA logic based on DNA (or defaults)
                fast_ma_period = int(dna.get("fast_ma", 9))
                slow_ma_period = int(dna.get("slow_ma", 21))
                
                if len(df) > slow_ma_period:
                    df['fast_ma'] = df['close'].rolling(window=fast_ma_period).mean()
                    df['slow_ma'] = df['close'].rolling(window=slow_ma_period).mean()
                    
                    fast_current = df['fast_ma'].iloc[-1]
                    slow_current = df['slow_ma'].iloc[-1]
                    fast_prev = df['fast_ma'].iloc[-2]
                    slow_prev = df['slow_ma'].iloc[-2]
                    
                    # Golden Cross (BUY)
                    if fast_prev < slow_prev and fast_current > slow_current:
                        lot = calculate_dynamic_lot(symbol, base_allocation=200.0)
                        if lot > 0:
                            place_order(symbol, "BUY", lot, "MOMENTUM_BURST")
                            time.sleep(60) # Wait 60s after trade to avoid duplicate entries
                            
                    # Death Cross (SELL)
                    elif fast_prev > slow_prev and fast_current < slow_current:
                        lot = calculate_dynamic_lot(symbol, base_allocation=200.0)
                        if lot > 0:
                            place_order(symbol, "SELL", lot, "MOMENTUM_BURST")
                            time.sleep(60)
            else:
                THREAD_STATUS[symbol] = "Waiting for ticks..."
            
            # Sleep 1 second for hyper-fast M1 polling
            time.sleep(1)
            
            # Dump status to JSON for the Dashboard
            try:
                with open(BASE_DIR / "thread_status.json", "w") as f:
                    json.dump(THREAD_STATUS, f)
            except: pass
            
        except Exception as e:
            THREAD_STATUS[symbol] = f"Error: {str(e)}"
            logging.error(f"[{symbol}] Thread Error: {e}")
            time.sleep(5)

def run_live_engine():
    if not init_mt5():
        return
        
    logging.info("Starting Multi-Threaded AI Strategy Executor...")
    dna_db = get_optimized_dna()
    symbols_to_trade = ["XAUUSD", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY", "XAGUSD", "AUDUSD"]
    
    # Start ThreadPoolExecutor (Adding +1 for the Trailing Manager)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(symbols_to_trade) + 1) as executor:
        # Submit the Trailing Engine Thread
        futures = {executor.submit(trailing_stop_manager, dna_db): "TRAILING_ENGINE"}
        
        # Submit the Strategy Polling Threads
        for sym in symbols_to_trade:
            futures[executor.submit(process_symbol, sym, dna_db)] = sym
            
        try:
            for future in concurrent.futures.as_completed(futures):
                sym_or_engine = futures[future]
                logging.info(f"[{sym_or_engine}] Thread Terminated.")
        except KeyboardInterrupt:
            logging.info("Shutting down live engine threads...")
            mt5.shutdown()

if __name__ == "__main__":
    run_live_engine()
