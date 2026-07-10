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

def calculate_dynamic_lot(symbol, sl_points_count, risk_pct=0.01):
    """
    STRICT 1% RISK ALGORITHM — hard capped at 0.10 lots max.
    """
    info = mt5.symbol_info(symbol)
    if not info: return 0.01
    
    account = mt5.account_info()
    if not account: return 0.01
        
    equity = account.equity
    risk_amount = equity * risk_pct
    
    tick_value = info.trade_tick_value
    if tick_value == 0 or sl_points_count <= 0:
        return 0.01
        
    true_volume = risk_amount / (sl_points_count * tick_value)
    
    step = info.volume_step if info.volume_step > 0 else 0.01
    scaled_lot = round(true_volume / step) * step
    
    raw_lot = max(info.volume_min, min(scaled_lot, info.volume_max))
    
    # ── HARD SAFETY CAP: Never exceed 0.10 lots per trade ─────────────────
    MAX_LOT_CAP = 0.10
    capped_lot = min(raw_lot, MAX_LOT_CAP)
    if raw_lot > MAX_LOT_CAP:
        logging.warning(f"[RISK_CAP] Lot size {raw_lot:.2f} capped to {MAX_LOT_CAP} for safety.")
    return capped_lot


def calculate_adx(symbol, timeframe=mt5.TIMEFRAME_M15, period=14):
    """
    Calculate ADX to detect trending vs ranging market.
    ADX < 20 = ranging (safe for mean reversion)
    ADX > 25 = strong trend (avoid mean reversion)
    """
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period * 3)
    if rates is None or len(rates) < period * 2:
        return 50.0  # Assume trending if data unavailable (conservative)
    
    df = pd.DataFrame(rates)
    df['tr'] = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    
    df['dm_pos'] = ((df['high'] - df['high'].shift()) > (df['low'].shift() - df['low'])).astype(float) * (df['high'] - df['high'].shift()).clip(lower=0)
    df['dm_neg'] = ((df['low'].shift() - df['low']) > (df['high'] - df['high'].shift())).astype(float) * (df['low'].shift() - df['low']).clip(lower=0)
    
    atr = df['tr'].rolling(period).mean()
    di_pos = 100 * (df['dm_pos'].rolling(period).mean() / atr)
    di_neg = 100 * (df['dm_neg'].rolling(period).mean() / atr)
    dx = (abs(di_pos - di_neg) / (di_pos + di_neg).replace(0, 1)) * 100
    adx = dx.rolling(period).mean().iloc[-1]
    return float(adx) if not pd.isna(adx) else 50.0


def is_daily_loss_breaker_hit(max_loss_pct=0.03):
    """
    Returns True if today's strategy losses exceeded max_loss_pct of balance.
    Halts new trades for the day if triggered.
    """
    try:
        account = mt5.account_info()
        if not account: return False
        from datetime import timedelta
        now = datetime.now()
        yesterday = now - timedelta(hours=24)
        deals = mt5.history_deals_get(yesterday, now)
        if not deals: return False
        daily_pnl = sum(d.profit for d in deals if d.magic == 888888 and d.entry == mt5.DEAL_ENTRY_OUT)
        if daily_pnl < 0:
            loss_pct = abs(daily_pnl) / account.balance
            if loss_pct >= max_loss_pct:
                logging.warning(f"[CIRCUIT_BREAKER] Strategy daily loss {loss_pct:.1%} >= {max_loss_pct:.0%}. Halting new entries.")
                return True
    except Exception as e:
        logging.error(f"[CIRCUIT_BREAKER] Error checking daily loss: {e}")
    return False

def place_order(symbol, trade_type, strat_name, magic_number=888888):
    """
    Executes the trade on MT5 with embedded ATR Stop-Loss to prevent naked positions.
    """
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logging.error(f"[{symbol}] Failed to get tick data (Market Closed?)")
        return None

    # Calculate ATR first
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 14)
        if rates is not None and len(rates) > 0:
            atr = sum((r['high'] - r['low']) for r in rates) / len(rates)
        else:
            atr = 0.0
    except:
        atr = 0.0

    info = mt5.symbol_info(symbol)
    point = info.point
    digits = info.digits
    
    if atr > 0:
        sl_points_raw = atr * 1.5
        tp_points_raw = atr * 3.0
    else:
        pip_mult = 10 if digits in [3, 5] else 1
        sl_points_raw = 50 * pip_mult * point
        tp_points_raw = 100 * pip_mult * point

    sl_points_count = sl_points_raw / point if point > 0 else 1000
    
    # Calculate strict 1% risk lot sizing
    lot = calculate_dynamic_lot(symbol, sl_points_count, risk_pct=0.01)

    action = mt5.ORDER_TYPE_BUY if trade_type == "BUY" else mt5.ORDER_TYPE_SELL
    price = tick.ask if action == mt5.ORDER_TYPE_BUY else tick.bid
    
    sl_price = price - sl_points_raw if action == mt5.ORDER_TYPE_BUY else price + sl_points_raw
    tp_price = price + tp_points_raw if action == mt5.ORDER_TYPE_BUY else price - tp_points_raw

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot),
        "type": action,
        "price": price,
        "sl": round(sl_price, digits),
        "tp": round(tp_price, digits),
        "deviation": 20,
        "magic": magic_number,
        "comment": strat_name,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"[{symbol}] Order Failed! Code: {result.retcode} Comment: {result.comment}")
        return None
        
    logging.info(f"[{symbol}] SUCCESS - Opened {trade_type} | Strat: {strat_name} | Lot: {lot} | SL: {sl_price}")
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
                # MT5 might be disconnected, try to reconnect
                if not init_mt5():
                    THREAD_STATUS["TRAILING_ENGINE"] = "Error: MT5 Disconnected"
                    time.sleep(5)
                    continue
                positions = () # Set to empty tuple if no positions after reconnecting
                
            for pos in positions:
                # Only manage our algorithmic trades
                if pos.magic != 888888:
                    continue
                    
                symbol = pos.symbol
                ticket = pos.ticket
                comment = pos.comment
                
                info = mt5.symbol_info(symbol)
                if not info: continue
                digits = info.digits
                point = info.point
                tick = mt5.symbol_info_tick(symbol)
                if tick is None or point == 0: continue
                price_current = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
                open_price = pos.price_open
                
                profit_points = (price_current - open_price) / point if pos.type == mt5.ORDER_TYPE_BUY else (open_price - price_current) / point
                
                # Dynamic ATR Trailing SL logic (TP1 / TP2 / TP3)
                try:
                    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 14)
                    if rates is not None and len(rates) > 0:
                        atr = sum((r['high'] - r['low']) for r in rates) / len(rates)
                    else:
                        atr = 0.0
                except:
                    atr = 0.0
                    
                atr_points = (atr / point) if point > 0 and atr > 0 else 150 # Fallback 150 points
                
                tp1 = atr_points * 1.0
                tp2 = atr_points * 2.0
                
                new_sl = pos.sl
                if profit_points >= tp2:
                    # Hit TP2, move SL to TP1
                    new_sl = open_price + (tp1 * point) if pos.type == mt5.ORDER_TYPE_BUY else open_price - (tp1 * point)
                elif profit_points >= tp1:
                    # Hit TP1, move SL to Breakeven (+15 points for fees)
                    new_sl = open_price + (15 * point) if pos.type == mt5.ORDER_TYPE_BUY else open_price - (15 * point)
                    
                new_sl = round(new_sl, digits)
                should_update = False
                if pos.type == mt5.ORDER_TYPE_BUY and new_sl > pos.sl and new_sl < price_current:
                    should_update = True
                elif pos.type == mt5.ORDER_TYPE_SELL and (pos.sl == 0.0 or new_sl < pos.sl) and new_sl > price_current:
                    should_update = True
                    
                if should_update and new_sl != pos.sl:
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": ticket,
                        "symbol": symbol,
                        "sl": new_sl,
                        "tp": pos.tp,
                    }
                    mt5.order_send(request)
                    logging.info(f"[{symbol}] Strategy Step-Trail: Locked SL to {new_sl}")
                        
            # Dump positions for Dashboard
            pos_data = []
            for pos in positions:
                tick = mt5.symbol_info_tick(pos.symbol)
                curr_price = 0.0
                if tick:
                    curr_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
                pos_data.append({
                    "symbol": pos.symbol,
                    "ticket": pos.ticket,
                    "type": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                    "volume": pos.volume,
                    "price_open": pos.price_open,
                    "price_current": curr_price,
                    "profit": pos.profit,
                    "comment": pos.comment
                })
            try:
                with open(BASE_DIR / "positions_status.json", "w") as f:
                    json.dump(pos_data, f)
            except: pass
            
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
    last_trade_time = 0
    
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
                init_mt5() # Attempt auto-reconnect
                time.sleep(5)
                continue

            # Step 1b: Daily circuit breaker check
            if is_daily_loss_breaker_hit(max_loss_pct=0.03):
                THREAD_STATUS[symbol] = "PAUSED: Daily loss limit hit"
                time.sleep(60)  # Check again in 60s
                continue
                
            # Map XM Global symbols back to standard DNA keys
            dna_symbol_key = symbol
            if symbol == "GOLD": dna_symbol_key = "XAUUSD"
            elif symbol == "SILVER": dna_symbol_key = "XAGUSD"
            
            # Extract ALL DNA assigned to this specific symbol
            symbol_dnas = {k: v for k, v in base_dna.items() if k.startswith(f"{dna_symbol_key}:")}
            
            if not symbol_dnas:
                THREAD_STATUS[symbol] = "No DNA assigned."
                time.sleep(5)
                continue
                
            THREAD_STATUS[symbol] = f"Active | Scanning {len(symbol_dnas)} Strategies"
            
            # Step 2: Prevent trade stacking. If we already have an open trade for this symbol, wait.
            open_positions = mt5.positions_get(symbol=symbol)
            if open_positions is not None and len([p for p in open_positions if p.magic == 888888]) > 0:
                THREAD_STATUS[symbol] = "Active | Trade currently open"
                time.sleep(5)
                continue
            
            # Fetch multi-timeframe data
            rates_m5  = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5,  0, 200)
            rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 200)
            rates_h1  = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1,  0, 200)

            if rates_m5 is None or len(rates_m5) < 50:
                THREAD_STATUS[symbol] = "Waiting for ticks..."
                time.sleep(2)
                continue

            df5  = pd.DataFrame(rates_m5)
            df15 = pd.DataFrame(rates_m15) if rates_m15 is not None else df5.copy()
            df1h = pd.DataFrame(rates_h1)  if rates_h1  is not None else df5.copy()
            for _df in [df5, df15, df1h]:
                for _c in ['close','open','high','low']:
                    _df[_c] = _df[_c].astype(float)

            def _rsi(df, p=14):
                d=df['close'].diff(); g=d.where(d>0,0).rolling(p).mean(); l=(-d.where(d<0,0)).rolling(p).mean()
                return (100-100/(1+g/l.replace(0,float('nan')))).iloc[-1]
            def _bb(df, p=20, s=2.0):
                m=df['close'].rolling(p).mean(); b=df['close'].rolling(p).std()*s
                return m.iloc[-1], (m+b).iloc[-1], (m-b).iloc[-1]
            def _macd(df):
                ef=df['close'].ewm(span=12).mean(); es=df['close'].ewm(span=26).mean()
                ln=ef-es; sg=ln.ewm(span=9).mean()
                return ln.iloc[-1], sg.iloc[-1], ln.iloc[-2], sg.iloc[-2]
            def _ema(df, n): return df['close'].ewm(span=n).mean()

            utc_h = datetime.utcnow().hour
            is_asian  = 0  <= utc_h < 8
            is_london = 7  <= utc_h < 13
            is_ny     = 12 <= utc_h < 21
            can_trade = time.time() - last_trade_time > 120

            # --- FULL 40-STRATEGY ALGORITHMIC FACTORY LOOP ---
            for strat_key, dna in symbol_dnas.items():
                if not can_trade: break
                sn = strat_key.split(":")[1]
                dr = dna.get("direction","BOTH")
                try:
                    if sn == "BOLLINGER_SQUEEZE":
                        mid, up, lo = _bb(df15); pr = df15['close'].iloc[-1]
                        if (up-lo)/mid < 0.004:
                            if pr > up and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                            elif pr < lo and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn in ("DAY_HIGH_BEARISH","ENHANCED_BEARISH"):
                        if is_london or is_ny:
                            dh = df1h['high'].iloc[-24:].max(); pr = df5['close'].iloc[-1]
                            if pr >= dh*0.9995 and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn in ("DAY_LOW_BULLISH","ENHANCED_BULLISH"):
                        if is_london or is_ny:
                            dl = df1h['low'].iloc[-24:].min(); pr = df5['close'].iloc[-1]
                            if pr <= dl*1.0005 and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                    elif sn in ("DAY_HIGH_LOW_TRADITIONAL","ULTIMATE_DAY_HIGH_LOW"):
                        dh=df1h['high'].iloc[-24:].max(); dl=df1h['low'].iloc[-24:].min(); pr=df5['close'].iloc[-1]
                        if pr > dh and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                        elif pr < dl and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "LONDON_BREAKOUT":
                        if 7 <= utc_h <= 10:
                            ah=df1h['high'].iloc[-9:-1].max(); al=df1h['low'].iloc[-9:-1].min(); pr=df5['close'].iloc[-1]
                            if pr > ah: place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                            elif pr < al: place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "ASIAN_RANGE_SCALP":
                        if is_asian:
                            ah=df1h['high'].iloc[-4:].max(); al=df1h['low'].iloc[-4:].min(); mid=(ah+al)/2; pr=df5['close'].iloc[-1]
                            if pr < mid and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                            elif pr > mid and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "NY_OPEN_REVERSAL":
                        if 12 <= utc_h <= 14:
                            r = _rsi(df15)
                            if r < 35 and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                            elif r > 65 and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "MORNING_BREAKOUT":
                        if 6 <= utc_h <= 9:
                            ph=df1h['high'].iloc[-12:-4].max(); pl=df1h['low'].iloc[-12:-4].min(); pr=df5['close'].iloc[-1]
                            if pr > ph: place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                            elif pr < pl: place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "MACD_DIVERGENCE":
                        ml,ms,mlp,msp = _macd(df15)
                        if mlp<msp and ml>ms and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                        elif mlp>msp and ml<ms and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "EMA_CROSSOVER":
                        e9=_ema(df15,9); e21=_ema(df15,21)
                        if e9.iloc[-2]<e21.iloc[-2] and e9.iloc[-1]>e21.iloc[-1] and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                        elif e9.iloc[-2]>e21.iloc[-2] and e9.iloc[-1]<e21.iloc[-1] and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "VWAP_BOUNCE":
                        df5['tp2']=(df5['high']+df5['low']+df5['close'])/3
                        vwap=(df5['tp2']*df5['volume']).cumsum()/df5['volume'].cumsum()
                        vv=vwap.iloc[-1]; pr=df5['close'].iloc[-1]; pv=df5['close'].iloc[-2]
                        if pv<vv and pr>vv and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                        elif pv>vv and pr<vv and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "ORDER_BLOCK_REVERSAL":
                        rc=df1h.tail(20); bob=rc[rc['close']>rc['open']]['high'].max(); bok=rc[rc['close']<rc['open']]['low'].min(); pr=df5['close'].iloc[-1]
                        if pr<=bok*1.001 and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                        elif pr>=bob*0.999 and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn in ("BREAKOUT","VOLATILITY_BREAKOUT","ATR_BREAK","RESIST_BREAK"):
                        rh=df15['high'].iloc[-21:-1].max(); rl=df15['low'].iloc[-21:-1].min(); pr=df5['close'].iloc[-1]
                        if pr>rh and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                        elif pr<rl and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn in ("MEAN_REVERSION","RSI_REVERSAL"):
                        if calculate_adx(symbol) >= 25: continue
                        r=_rsi(df5)
                        if r<30 and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                        elif r>70 and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn in ("TREND_FOLLOWING","BULL_TREND_FOLLOWER","BEAR_TREND_FOLLOWER","MOMENTUM_BURST"):
                        if calculate_adx(symbol) < 20: continue
                        e9=_ema(df15,9); e50=_ema(df15,50); r=_rsi(df15)
                        if e9.iloc[-1]>e50.iloc[-1] and 45<r<70 and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                        elif e9.iloc[-1]<e50.iloc[-1] and 30<r<55 and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif "GAP" in sn:
                        if len(df1h)>=2:
                            pc=df1h['close'].iloc[-2]; co=df1h['open'].iloc[-1]; cc=df1h['close'].iloc[-1]; gp=(co-pc)/pc
                            if abs(gp)>0.001:
                                if gp>0 and cc<co and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                                elif gp<0 and cc>co and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "OPENING_DRIVE":
                        if utc_h in [8,9,13,14]:
                            e9=_ema(df5,9); e21=_ema(df5,21)
                            if e9.iloc[-1]>e21.iloc[-1] and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                            elif e9.iloc[-1]<e21.iloc[-1] and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "SHORT_SQUEEZE":
                        r=_rsi(df5); _,up,_=_bb(df5)
                        if r>60 and df5['close'].iloc[-1]>up and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "LONG_LIQUIDATION":
                        r=_rsi(df5); _,_,lo=_bb(df5)
                        if r<40 and df5['close'].iloc[-1]<lo and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn in ("RANGE_CONTRACTION","EARLY_BREAKDOWN"):
                        rg=(df1h['high']-df1h['low']).tail(5); pr=df5['close'].iloc[-1]; op=df1h['open'].iloc[-1]
                        if rg.iloc[-1]<rg.mean()*0.6:
                            if pr<op and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                            elif pr>op and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "VOLUME_CLIMAX":
                        av=df5['volume'].rolling(20).mean().iloc[-1]; pr=df5['close'].iloc[-1]; pv=df5['close'].iloc[-2]
                        if df5['volume'].iloc[-1]>av*2:
                            if pr<pv and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                            elif pr>pv and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "WIDE_RANGE_RIDER":
                        lr=df1h['high'].iloc[-1]-df1h['low'].iloc[-1]; ar=(df1h['high']-df1h['low']).rolling(10).mean().iloc[-1]
                        if lr>ar*1.5:
                            pr=df5['close'].iloc[-1]; op=df1h['open'].iloc[-1]
                            if pr>op and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                            elif pr<op and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "NEWS_BREAKOUT_STRADDLE":
                        if utc_h in [8,9,13,14]:
                            rh=df15['high'].iloc[-12:].max(); rl=df15['low'].iloc[-12:].min(); pr=df5['close'].iloc[-1]
                            if pr>rh: place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                            elif pr<rl: place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn == "INSTITUTIONAL_SUPPORT":
                        pr=df5['close'].iloc[-1]; info=mt5.symbol_info(symbol)
                        if info:
                            rf=10**(info.digits-2); nr=round(pr*rf)/rf
                            if abs(pr-nr)/pr<0.0005:
                                r=_rsi(df5)
                                if r<45 and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                                elif r>55 and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                    elif sn in ("ZERO_HERO","MAGIC_SQUARE","AI_ENHANCED","SCALPING","PIP_BLAST","SWAP_ARBITRAGE"):
                        e9=_ema(df5,9); e21=_ema(df5,21); r=_rsi(df5,7)
                        if e9.iloc[-1]>e21.iloc[-1] and r>55 and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn); last_trade_time=time.time(); can_trade=False
                        elif e9.iloc[-1]<e21.iloc[-1] and r<45 and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn); last_trade_time=time.time(); can_trade=False
                except Exception as se:
                    logging.error(f"[{symbol}] Strategy {sn} error: {se}")
                    continue
            
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
    symbols_to_trade = ["GOLD", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY", "SILVER", "AUDUSD"]
    
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
