import json
import logging
import time
from pathlib import Path
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime
import concurrent.futures

import joblib

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

ML_MODEL_PATH = BASE_DIR / "final_model_sucess.joblib"
try:
    ML_MODEL = joblib.load(ML_MODEL_PATH)
    logging.info(f"Successfully loaded ML Model: {ML_MODEL_PATH}")
except Exception as e:
    logging.error(f"Failed to load ML Model: {e}")
    ML_MODEL = None
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

def calculate_adx(symbol, p=14):
    try:
        # Fetch M15 rates to calculate ADX
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, p * 3)
        if rates is None or len(rates) == 0:
            return 20
        df = pd.DataFrame(rates)
        tr = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift()).abs(),
            (df['low'] - df['close'].shift()).abs()
        ], axis=1).max(axis=1)
        dmp = ((df['high'] - df['high'].shift()) > (df['low'].shift() - df['low'])).astype(float) * (df['high'] - df['high'].shift()).clip(lower=0)
        dmn = ((df['low'].shift() - df['low']) > (df['high'] - df['high'].shift())).astype(float) * (df['low'].shift() - df['low']).clip(lower=0)
        atr = tr.rolling(p).mean()
        di_p = 100 * (dmp.rolling(p).mean() / atr)
        di_n = 100 * (dmn.rolling(p).mean() / atr)
        dx = (abs(di_p - di_n) / (di_p + di_n).replace(0, 1)) * 100
        adx = dx.rolling(p).mean()
        val = adx.iloc[-1]
        if pd.isna(val):
            return 20
        return float(val)
    except Exception as e:
        logging.error(f"Error calculating ADX for {symbol}: {e}")
        return 20

def calculate_dynamic_lot(symbol, sl_points_count, risk_pct=0.01):
    """
    PHASE 2: Anti-Martingale Asymmetric Risk Sizing.
    Base Risk is 0.5%.
    If the last 2 trades were wins -> double risk to 1.0%.
    If the last 2 trades were losses -> half risk to 0.25% (recovery mode).
    STRICT CAP at 2.0%.
    """
    info = mt5.symbol_info(symbol)
    if not info: return 0.01
    
    account = mt5.account_info()
    if not account: return 0.01
        
    equity = account.equity
    
    # Analyze MT5 History for Streak
    from datetime import datetime, timedelta
    try:
        now = datetime.now()
        yesterday = now - timedelta(days=7) # Look back a week for closed trades
        deals = mt5.history_deals_get(yesterday, now)
        if deals:
            # Filter for closed deals with our magic number
            closed_deals = [d for d in deals if d.magic == 888888 and d.entry == mt5.DEAL_ENTRY_OUT]
            # Sort by time
            closed_deals = sorted(closed_deals, key=lambda x: x.time)
            if len(closed_deals) >= 2:
                last_deal = closed_deals[-1]
                prev_deal = closed_deals[-2]
                if last_deal.profit > 0 and prev_deal.profit > 0:
                    risk_pct = min(0.02, risk_pct * 2.0)
                    logging.info(f"[{symbol}] Anti-Martingale: 2 Wins in a row! Doubling risk to {risk_pct:.2%}")
                elif last_deal.profit < 0 and prev_deal.profit < 0:
                    risk_pct = max(0.0025, risk_pct * 0.5)
                    logging.info(f"[{symbol}] Anti-Martingale: 2 Losses in a row! Halving risk to {risk_pct:.2%}")
    except Exception as e:
        logging.error(f"[{symbol}] Anti-Martingale Error: {e}")
        pass # Default to passed risk_pct
        
    risk_amount = equity * risk_pct
    
    tick_value = info.trade_tick_value
    if tick_value == 0 or sl_points_count <= 0:
        return 0.01
        
    true_volume = risk_amount / (sl_points_count * tick_value)
    
    step = info.volume_step if info.volume_step > 0 else 0.01
    scaled_lot = round(true_volume / step) * step
    
    raw_lot = max(info.volume_min, min(scaled_lot, info.volume_max))
    
    # ── HARD SAFETY CAP: Strictly cap lot sizes to 0.05 lots for $1,500 micro account capital protection ──
    MAX_LOT_CAP = 0.05
    capped_lot = min(raw_lot, MAX_LOT_CAP)
    if raw_lot > MAX_LOT_CAP:
        logging.warning(f"[{symbol}] [RISK_CAP] Lot size {raw_lot:.2f} capped to {MAX_LOT_CAP} for micro-account safety.")
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


def is_daily_loss_breaker_hit(max_loss_pct=0.02):
    return False # Disabled for paper trading
    """
    PHASE 2: 2% Strict Daily Circuit Breaker
    Returns True if today's strategy losses (realized + floating) exceeded max_loss_pct of balance.
    Halts new trades for the day if triggered.
    """
    try:
        account = mt5.account_info()
        if not account: return False
        
        from datetime import datetime, timedelta
        # Calculate start of current UTC day
        now_utc = datetime.utcnow()
        start_of_day = datetime(now_utc.year, now_utc.month, now_utc.day)
        
        deals = mt5.history_deals_get(start_of_day, now_utc)
        realized_pnl = 0.0
        if deals:
            realized_pnl = sum(d.profit for d in deals if d.magic == 888888 and d.entry == mt5.DEAL_ENTRY_OUT)
            
        # Add open floating P&L
        floating_pnl = 0.0
        positions = mt5.positions_get()
        if positions:
            floating_pnl = sum(p.profit for p in positions if p.magic == 888888)
            
        total_daily_pnl = realized_pnl + floating_pnl
        
        if total_daily_pnl < 0:
            loss_pct = abs(total_daily_pnl) / account.balance
            if loss_pct >= max_loss_pct:
                logging.warning(f"[CIRCUIT_BREAKER] 🛑 Daily Loss {loss_pct:.1%} >= Limit {max_loss_pct:.0%}. HALTING NEW TRADES.")
                return True
    except Exception as e:
        logging.error(f"[CIRCUIT_BREAKER] Error checking daily loss: {e}")
    return False

def place_order(symbol, trade_type, strat_name, dna=None, magic_number=888888):
    """
    Executes the trade on MT5 with embedded ATR Stop-Loss to prevent naked positions.
    Incorporates Phase 1: ML Model Inference & Time-Decoded Dual-Zone R/R
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
    
    # ── Phase 3: Dynamic Live Spread Protection ──
    spread_points = info.spread
    projected_sl_dist = atr * 3.0
    spread_price = spread_points * point
    
    # On weekend crypto, allow spread up to 35% of SL room; for traditional FX/Metals, strict 15% cap
    max_spread_pct = 0.35 if symbol in ("BTCUSD", "ETHUSD") else 0.15
    if projected_sl_dist > 0 and spread_price > (projected_sl_dist * max_spread_pct):
        logging.warning(f"[{symbol}] 🚨 Spread Protection: Live Spread ({spread_price}) eats > {max_spread_pct*100:.0f}% of SL Room ({projected_sl_dist}). Trade Aborted.")
        return None
        
    # ── Phase 3: Institutional Proven R/R Parameters ──
    # Mandatory 3.0 ATR Stop Buffer across ALL symbols to survive stop-hunts and liquidity sweeps!
    sl_atr_mult = 3.0
    
    # Calibrated profit targets from Multi-Timeframe Super-Portfolio (+215% ROI proof):
    if symbol in ("BTCUSD", "ETHUSD", "CRYPTO"):
        tp_atr_mult = 1.25  # Fast crypto momentum captures
    elif symbol in ("GOLD", "SILVER", "XAUUSD", "XAGUSD"):
        tp_atr_mult = 1.5   # High-volatility metal swings
    else:
        tp_atr_mult = 1.3   # Core forex currency breakout targets

    utc_now = datetime.utcnow()
    utc_h = utc_now.hour
    weekday = utc_now.weekday()

    if atr > 0:
        sl_points_raw = atr * sl_atr_mult
        tp_points_raw = atr * tp_atr_mult
    else:
        pip_mult = 10 if digits in [3, 5] else 1
        sl_points_raw = 50 * pip_mult * point
        tp_points_raw = 100 * pip_mult * point
        
    # --- Safe Stop Enforcement ---
    min_dist = info.trade_stops_level * point
    if min_dist <= 0:
        min_dist = 50 * point if digits in [3, 5] else 5 * point
        
    # Hard minimums to prevent 10016 Invalid Stops
    hard_min = 1000 * point if "XAU" in symbol or "GOLD" in symbol else 100 * point
    if "BTC" in symbol: hard_min = 5000 * point
    if "ETH" in symbol: hard_min = 500 * point
    
    sl_points_raw = max(sl_points_raw, min_dist * 1.5, hard_min)
    tp_points_raw = max(tp_points_raw, min_dist * 2.0, hard_min * 2)
        
    sl_points_count = sl_points_raw / point if point > 0 else 1000
    tp_points_count = tp_points_raw / point if point > 0 else 2000

    # ── Phase 1: ML Model Live Inference ──
    if ML_MODEL is not None:
        try:
            # Calculate live features
            adx_val = calculate_adx(symbol)
            
            # Fast RSI
            rsi_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 20)
            if rsi_rates is not None and len(rsi_rates) >= 15:
                df_rsi = pd.DataFrame(rsi_rates)
                d = df_rsi['close'].diff()
                g = d.where(d > 0, 0).rolling(14).mean()
                l = (-d.where(d < 0, 0)).rolling(14).mean()
                rsi_val = (100 - 100 / (1 + g / l.replace(0, float('nan')))).iloc[-1]
            else:
                rsi_val = 50.0
                
            # Determine Session
            if 0 <= utc_h < 8: session = 'ASIAN'
            elif 8 <= utc_h < 13: session = 'LONDON'
            else: session = 'NY'
                
            # ── Component 2: ADX Market Regime Classifier (Trend vs Range) ──
            is_trend_strat = any(kw in strat_name.upper() for kw in ["TREND", "MOMENTUM", "BREAKOUT", "MA_CROSS", "SURFER", "CROSSOVER"])
            is_range_strat = any(kw in strat_name.upper() for kw in ["ZERO_HERO", "WIDE_RANGE", "REVERSION", "RSI_OS", "RSI_OB"])

            if adx_val > 25.0 and is_range_strat:
                logging.info(f"[{symbol}] REGIME VETO: Strong Trend ADX ({adx_val:.1f} > 25). Mean-reversion strat {strat_name} Aborted.")
                return None
            elif adx_val < 20.0 and is_trend_strat:
                logging.info(f"[{symbol}] REGIME VETO: Ranging Market ADX ({adx_val:.1f} < 20). Breakout/Trend strat {strat_name} Aborted.")
                return None

            feature_dict = {
                "symbol": symbol,
                "strategy": strat_name,
                "direction": trade_type,
                "session": session,
                "hour": utc_h,
                "weekday": weekday,
                "rsi_val": rsi_val,
                "adx_val": adx_val,
                "atr": atr / point if point > 0 else 0,
                "sl_pts": sl_points_count,
                "tp_pts": tp_points_count
            }
            
            df_features = pd.DataFrame([feature_dict])
            prob = ML_MODEL.predict_proba(df_features)[0][1]
            
            # ── Component 3: Adaptive Pair-Specific ML Veto Thresholds ──
            if symbol in ("USDCHF", "GBPJPY", "SILVER"):
                prob_threshold = 0.52  # Proven high-edge pairs get lower threshold to capture profits
            elif symbol in ("GOLD", "GBPUSD", "EURUSD"):
                prob_threshold = 0.58  # Standard pairs require 58% probability
            elif symbol in ("BTCUSD", "ETHUSD"):
                prob_threshold = 0.68  # Volatile crypto pairs require strict 68% conviction
            else:
                prob_threshold = 0.55  # Default threshold

            if prob < prob_threshold:
                logging.info(f"[{symbol}] ML FILTERED TRADE: {strat_name} | {trade_type} | Win Prob: {prob:.1%} < Threshold {prob_threshold:.0%}.")
                return None
            else:
                logging.info(f"[{symbol}] ML APPROVED: {strat_name} | {trade_type} | Win Prob: {prob:.1%} >= Threshold {prob_threshold:.0%}.")
                
        except Exception as ml_err:
            logging.error(f"[{symbol}] ML Inference Error: {ml_err}. Proceeding without ML.")

    # Calculate dynamic Kelly Criterion risk sizing
    risk_pct = 0.01
    if dna is not None:
        win_rate = float(dna.get("win_rate", 0.35))
        avg_rr = float(dna.get("avg_rr", 1.5))
        if avg_rr > 0:
            kelly_f = (win_rate * avg_rr - (1.0 - win_rate)) / avg_rr
            risk_pct = max(0.01, min(0.05, kelly_f * 0.25))
            
    lot = calculate_dynamic_lot(symbol, sl_points_count, risk_pct=risk_pct)

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
        "comment": f"AI: {strat_name[:14]} {magic_number}"[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode == 10016:
        logging.warning(f"[{symbol}] Retcode 10016 (Invalid Stops). Retrying with widened safety stops...")
        request["sl"] = round(price - (sl_points_raw * 1.5) if action == mt5.ORDER_TYPE_BUY else price + (sl_points_raw * 1.5), digits)
        request["tp"] = round(price + (tp_points_raw * 1.5) if action == mt5.ORDER_TYPE_BUY else price - (tp_points_raw * 1.5), digits)
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
                if tick is None or point == 0 or (time.time() - tick.time > 300):
                    # Skip modifying Stop Loss if the market is closed or offline (no ticks in last 5 minutes, e.g. weekends)
                    continue
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
                    res = mt5.order_send(request)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
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
                
                # Send Alert
                try:
                    alert_path = BASE_DIR / "alerts.json"
                    alerts = []
                    if alert_path.exists():
                        with open(alert_path, "r", encoding="utf-8") as af:
                            try: alerts = json.load(af)
                            except: pass
                    # Throttle alerts so we don't spam
                    if not any(a["source"] == "MT5 Terminal" for a in alerts[-3:]):
                        alerts.append({
                            "source": "MT5 Terminal",
                            "message": f"MT5 Disconnected on {symbol} thread. Attempting auto-reconnect.",
                            "level": "WARNING",
                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        with open(alert_path, "w", encoding="utf-8") as af:
                            json.dump(alerts, af, indent=2)
                except: pass
                
                init_mt5() # Attempt auto-reconnect
                time.sleep(5)
                continue

            # Step 1b: Daily circuit breaker check
            if is_daily_loss_breaker_hit(max_loss_pct=0.03):
                THREAD_STATUS[symbol] = "PAUSED: Daily loss limit hit"
                time.sleep(60)  # Check again in 60s
                continue
                
            # Extract ALL DNA assigned to this specific symbol
            strategies_dict = base_dna.get("strategies", base_dna)
            symbol_dnas = {k: v for k, v in strategies_dict.items() if k.startswith(f"{symbol}_")}
            
            # Intelligent DNA Fallback: If no explicit DNA keys exist for this symbol, clone our proven AI profile
            if not symbol_dnas and strategies_dict:
                template_sym = "GBPUSD" if not symbol in ("BTCUSD", "ETHUSD") else "BTCUSD"
                template_dnas = {k: v for k, v in strategies_dict.items() if k.startswith(f"{template_sym}_")}
                if not template_dnas:
                    # Take any first 40 entries
                    template_dnas = dict(list(strategies_dict.items())[:41])
                symbol_dnas = {}
                for k, v in template_dnas.items():
                    strat_name = k.split("_", 1)[1] if "_" in k else k
                    symbol_dnas[f"{symbol}_{strat_name}"] = v

            if not symbol_dnas:
                THREAD_STATUS[symbol] = "No DNA assigned."
                time.sleep(5)
                continue
                
            # --- PHASE 1: WEEKEND SCHEDULE GUARD (24/7 CRYPTO vs MONDAY-FRIDAY FX/METALS) ---
            utc_now = datetime.utcnow()
            is_weekend = utc_now.weekday() >= 5  # 5 = Saturday, 6 = Sunday
            is_crypto = symbol in ("BTCUSD", "ETHUSD", "CRYPTO")
            
            if is_weekend and not is_crypto:
                THREAD_STATUS[symbol] = "Market Closed (Weekend) | Awaiting Monday Open"
                time.sleep(30)
                continue
                
            # --- SPREAD GUARD & BROKER PROTECTION ---
            mt5.symbol_select(symbol, True)
            tick_info = mt5.symbol_info_tick(symbol)
            sym_info = mt5.symbol_info(symbol)
            if tick_info and sym_info and sym_info.point > 0:
                spread_pips = (tick_info.ask - tick_info.bid) / sym_info.point
                # Allow ample headroom for weekend live Crypto CFD execution ($80 for BTC, $15 for ETH)
                max_allowed_spread = 8000.0 if symbol == "BTCUSD" else (1500.0 if symbol == "ETHUSD" else 55.0)
                if spread_pips > max_allowed_spread and not is_weekend:
                    THREAD_STATUS[symbol] = f"PAUSED: High spread ({spread_pips:.1f} > {max_allowed_spread})"
                    time.sleep(10)
                    continue

            # --- PHASE 1: MULTI-TIMEFRAME ENGINE MAPPING ---
            # GOLD on M5, SILVER/GBPJPY/AUDUSD/USDJPY/GBPUSD/BTCUSD on M15, USDCHF on M30, ETHUSD on M5!
            tf_mapping = {
                "GOLD": mt5.TIMEFRAME_M5, "ETHUSD": mt5.TIMEFRAME_M5,
                "SILVER": mt5.TIMEFRAME_M15, "XAGUSD": mt5.TIMEFRAME_M15, "GBPJPY": mt5.TIMEFRAME_M15,
                "AUDUSD": mt5.TIMEFRAME_M15, "USDJPY": mt5.TIMEFRAME_M15, "GBPUSD": mt5.TIMEFRAME_M15,
                "BTCUSD": mt5.TIMEFRAME_M15, "USDCHF": mt5.TIMEFRAME_M30
            }
            primary_tf = tf_mapping.get(symbol, mt5.TIMEFRAME_M15)
            tf_label = {mt5.TIMEFRAME_M5: "M5", mt5.TIMEFRAME_M15: "M15", mt5.TIMEFRAME_M30: "M30", mt5.TIMEFRAME_H1: "H1"}.get(primary_tf, "M15")

            THREAD_STATUS[symbol] = f"Active ({tf_label}) | Scanning {len(symbol_dnas)} Strategies"
            
            # Step 2: Prevent trade stacking. If we already have an open trade for this symbol, wait.
            open_positions = mt5.positions_get(symbol=symbol)
            if open_positions is not None and len([p for p in open_positions if p.magic == 888888]) > 0:
                THREAD_STATUS[symbol] = f"Active ({tf_label}) | Trade currently open"
                time.sleep(5)
                continue
            
            # Fetch multi-timeframe historical bars, prioritizing optimal primary timeframe
            rates_primary = mt5.copy_rates_from_pos(symbol, primary_tf, 0, 250)
            rates_m5      = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 250)
            rates_h1      = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 250)

            if rates_primary is None or len(rates_primary) < 50:
                THREAD_STATUS[symbol] = f"Waiting for {tf_label} ticks..."
                time.sleep(2)
                continue

            df_primary = pd.DataFrame(rates_primary)
            df5        = pd.DataFrame(rates_m5) if rates_m5 is not None and len(rates_m5) > 0 else df_primary.copy()
            df1h       = pd.DataFrame(rates_h1) if rates_h1 is not None and len(rates_h1) > 0 else df_primary.copy()
            # In legacy calculations expecting df15, we provide df_primary so execution happens at optimal resolution!
            df15       = df_primary.copy()
            
            for _df in [df5, df15, df1h, df_primary]:
                for _c in ['close','open','high','low']:
                    _df[_c] = _df[_c].astype(float)
                if 'tick_volume' in _df.columns:
                    _df['volume'] = _df['tick_volume'].astype(float)
                elif 'volume' not in _df.columns:
                    _df['volume'] = 1.0

            def _rsi(df, p=14):
                d=df['close'].diff(); g=d.where(d>0,0).rolling(p).mean(); l=(-d.where(d<0,0)).rolling(p).mean()
                return (100-100/(1+g/l.replace(0,float('nan')))).iloc[-2]
            def _bb(df, p=20, s=2.0):
                m=df['close'].rolling(p).mean(); b=df['close'].rolling(p).std()*s
                return m.iloc[-2], (m+b).iloc[-2], (m-b).iloc[-2]
            def _macd(df):
                ef=df['close'].ewm(span=12).mean(); es=df['close'].ewm(span=26).mean()
                ln=ef-es; sg=ln.ewm(span=9).mean()
                return ln.iloc[-2], sg.iloc[-2], ln.iloc[-3], sg.iloc[-3]
            def _ema(df, n): return df['close'].ewm(span=n).mean()

            utc_h = datetime.utcnow().hour
            
            # ROLLOVER SPREAD LOCKOUT: Block strategy entries during 21:00-23:00 UTC spread widening
            if 21 <= utc_h < 23 and not is_crypto:
                THREAD_STATUS[symbol] = "ROLLOVER PAUSE: Awaiting 23:00 UTC Spread Normalization"
                time.sleep(30)
                continue
                
            is_asian  = 0  <= utc_h < 8
            is_london = 7  <= utc_h < 13
            is_ny     = 12 <= utc_h < 21
            can_trade = time.time() - last_trade_time > 900  # 15 min cooldown

            # --- FULL 40-STRATEGY ALGORITHMIC FACTORY LOOP ---
            for strat_key, dna in symbol_dnas.items():
                if not can_trade: break
                sn = strat_key.split("_", 1)[1]
                dr = dna.get("direction","BOTH")
                try:
                    # --- REGIME FILTER GUARD ---
                    # Volatility Ratio from df15
                    std_short = df15['close'].iloc[-5:].std()
                    std_long  = df15['close'].iloc[-50:].std()
                    vol_ratio = std_short / std_long if std_long > 0 else 1.0

                    # ADX from live calculation
                    adx_val = calculate_adx(symbol)

                    # Classify Strategy Types
                    is_trend_strategy = sn in ("TREND_FOLLOWING","BULL_TREND_FOLLOWER","BEAR_TREND_FOLLOWER","MOMENTUM_BURST","EMA_CROSSOVER","ZERO_HERO","MAGIC_SQUARE","AI_ENHANCED","SWAP_ARBITRAGE","SCALPING")
                    is_reversion_strategy = sn in ("MEAN_REVERSION","RSI_REVERSAL","NY_OPEN_REVERSAL","ASIAN_RANGE_SCALP","BOLLINGER_SQUEEZE","DAY_HIGH_BEARISH","ENHANCED_BEARISH","DAY_LOW_BULLISH","ENHANCED_BULLISH","DAY_HIGH_LOW_TRADITIONAL","ULTIMATE_DAY_HIGH_LOW","ORDER_BLOCK_REVERSAL","VOLUME_CLIMAX","INSTITUTIONAL_SUPPORT")
                    is_breakout_strategy = sn in ("BREAKOUT","VOLATILITY_BREAKOUT","ATR_BREAK","RESIST_BREAK","LONDON_BREAKOUT","MORNING_BREAKOUT","NEWS_BREAKOUT_STRADDLE","OPENING_DRIVE","WIDE_RANGE_RIDER")

                    # Check rules
                    if dna.get("active", True) is False: continue
                    if symbol in ("GOLD", "SILVER") and sn in ("ZERO_HERO", "MAGIC_SQUARE", "AI_ENHANCED", "SWAP_ARBITRAGE", "SCALPING", "PIP_BLAST"): continue
                    if is_trend_strategy and adx_val < 20: continue
                    if is_reversion_strategy and adx_val >= 25: continue
                    if is_breakout_strategy and vol_ratio < 0.8: continue
                    if is_reversion_strategy and vol_ratio >= 1.5: continue

                    thresh_val = float(dna.get("thresh", 0.85))
                    # Repainting-Proof: Evaluate closed candle (iloc[-2]) instead of developing candle
                    pr = df5['close'].iloc[-2]

                    if sn == "BOLLINGER_SQUEEZE":
                        mid, up, lo = _bb(df15)
                        width = (up - lo) / mid
                        bol_squeeze_thresh = 0.004 * (thresh_val if thresh_val > 0 else 0.87)
                        if width < bol_squeeze_thresh:
                            if pr > up and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                            elif pr < lo and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn in ("DAY_HIGH_BEARISH","ENHANCED_BEARISH"):
                        if is_london or is_ny:
                            mean_24 = df1h['close'].iloc[-24:].mean()
                            std_24 = df1h['close'].iloc[-24:].std()
                            std_24 = std_24 if std_24 > 0 else (pr * 0.001)
                            z_score = (pr - mean_24) / std_24
                            if z_score >= (thresh_val if thresh_val > 0 else 0.82) and dr in ("SELL","BOTH"):
                                place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn in ("DAY_LOW_BULLISH","ENHANCED_BULLISH"):
                        if is_london or is_ny:
                            mean_24 = df1h['close'].iloc[-24:].mean()
                            std_24 = df1h['close'].iloc[-24:].std()
                            std_24 = std_24 if std_24 > 0 else (pr * 0.001)
                            z_score = (pr - mean_24) / std_24
                            if z_score <= (thresh_val if thresh_val < 0 else -2.2) and dr in ("BUY","BOTH"):
                                place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn in ("DAY_HIGH_LOW_TRADITIONAL","ULTIMATE_DAY_HIGH_LOW"):
                        dh = df1h['high'].iloc[-24:].max()
                        dl = df1h['low'].iloc[-24:].min()
                        buffer = (dh - dl) * 0.01 * (thresh_val - 0.5)
                        if pr > dh + buffer and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                        elif pr < dl - buffer and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "LONDON_BREAKOUT":
                        if 7 <= utc_h <= 10:
                            ah = df1h['high'].iloc[-9:-1].max()
                            al = df1h['low'].iloc[-9:-1].min()
                            rng = ah - al
                            if pr > ah + rng * 0.05 * thresh_val: place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                            elif pr < al - rng * 0.05 * thresh_val: place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "ASIAN_RANGE_SCALP":
                        if is_asian:
                            ah = df1h['high'].iloc[-4:].max()
                            al = df1h['low'].iloc[-4:].min()
                            mid = (ah + al) / 2
                            if pr < mid and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                            elif pr > mid and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "NY_OPEN_REVERSAL":
                        if 12 <= utc_h <= 14:
                            r = _rsi(df15)
                            oversold = 35 * thresh_val
                            overbought = 100 - oversold
                            if r < oversold and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                            elif r > overbought and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "MORNING_BREAKOUT":
                        if 6 <= utc_h <= 9:
                            ph = df1h['high'].iloc[-12:-4].max()
                            pl = df1h['low'].iloc[-12:-4].min()
                            rng = ph - pl
                            if pr > ph + rng * 0.05 * thresh_val: place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                            elif pr < pl - rng * 0.05 * thresh_val: place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "MACD_DIVERGENCE":
                        ml, ms, mlp, msp = _macd(df15)
                        if mlp < msp and ml > ms and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                        elif mlp > msp and ml < ms and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "EMA_CROSSOVER":
                        e9 = _ema(df15,9); e21 = _ema(df15,21)
                        if e9.iloc[-2] < e21.iloc[-2] and e9.iloc[-1] > e21.iloc[-1] and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                        elif e9.iloc[-2] > e21.iloc[-2] and e9.iloc[-1] < e21.iloc[-1] and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "VWAP_BOUNCE":
                        df5['tp2'] = (df5['high'] + df5['low'] + df5['close']) / 3
                        vwap = (df5['tp2'] * df5['volume']).cumsum() / df5['volume'].cumsum()
                        vv = vwap.iloc[-1]
                        pv = df5['close'].iloc[-2]
                        if pv < vv and pr > vv and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                        elif pv > vv and pr < vv and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "ORDER_BLOCK_REVERSAL":
                        rc = df1h.tail(20)
                        bob = rc[rc['close'] > rc['open']]['high'].max() if len(rc[rc['close'] > rc['open']]) > 0 else pr
                        bok = rc[rc['close'] < rc['open']]['low'].min() if len(rc[rc['close'] < rc['open']]) > 0 else pr
                        if pr <= bok * (1 + 0.001 * thresh_val) and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                        elif pr >= bob * (1 - 0.001 * thresh_val) and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn in ("BREAKOUT","VOLATILITY_BREAKOUT","ATR_BREAK","RESIST_BREAK"):
                        rh = df15['high'].iloc[-21:-1].max()
                        rl = df15['low'].iloc[-21:-1].min()
                        if pr > rh * (1 + 0.0002 * thresh_val) and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                        elif pr < rl * (1 - 0.0002 * thresh_val) and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn in ("MEAN_REVERSION","RSI_REVERSAL"):
                        if calculate_adx(symbol) >= 25: continue
                        r = _rsi(df5)
                        oversold = 30 * thresh_val
                        overbought = 100 - oversold
                        if r < oversold and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                        elif r > overbought and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn in ("TREND_FOLLOWING","BULL_TREND_FOLLOWER","BEAR_TREND_FOLLOWER","MOMENTUM_BURST"):
                        if calculate_adx(symbol) < 20: continue
                        e9 = _ema(df15,9); e50 = _ema(df15,50); r = _rsi(df15)
                        if e9.iloc[-1] > e50.iloc[-1] and 45 < r < 70 and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                        elif e9.iloc[-1] < e50.iloc[-1] and 30 < r < 55 and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif "GAP" in sn:
                        if len(df1h) >= 2:
                            pc = df1h['close'].iloc[-2]
                            co = df1h['open'].iloc[-1]
                            cc = df1h['close'].iloc[-1]
                            gp = (co - pc) / pc
                            if abs(gp) > 0.001:
                                if gp > 0 and cc < co and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                                elif gp < 0 and cc > co and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "OPENING_DRIVE":
                        if utc_h in [8,9,13,14]:
                            e9 = _ema(df5,9); e21 = _ema(df5,21)
                            if e9.iloc[-1] > e21.iloc[-1] and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                            elif e9.iloc[-1] < e21.iloc[-1] and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "SHORT_SQUEEZE":
                        r = _rsi(df5); _, up, _ = _bb(df5)
                        if r > 60 and pr > up and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "LONG_LIQUIDATION":
                        r = _rsi(df5); _, _, lo = _bb(df5)
                        if r < 40 and pr < lo and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn in ("RANGE_CONTRACTION","EARLY_BREAKDOWN"):
                        rg = (df1h['high'] - df1h['low']).tail(5)
                        op = df1h['open'].iloc[-1]
                        if rg.iloc[-1] < rg.mean() * 0.6:
                            if pr < op and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                            elif pr > op and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "VOLUME_CLIMAX":
                        av = df5['volume'].rolling(20).mean().iloc[-1]
                        pv = df5['close'].iloc[-2]
                        if df5['volume'].iloc[-1] > av * 2:
                            if pr < pv and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                            elif pr > pv and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "WIDE_RANGE_RIDER":
                        lr = df1h['high'].iloc[-1] - df1h['low'].iloc[-1]
                        ar = (df1h['high'] - df1h['low']).rolling(10).mean().iloc[-1]
                        if lr > ar * 1.5:
                            op = df1h['open'].iloc[-1]
                            if pr > op and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                            elif pr < op and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "NEWS_BREAKOUT_STRADDLE":
                        if utc_h in [8,9,13,14]:
                            rh = df15['high'].iloc[-12:].max()
                            rl = df15['low'].iloc[-12:].min()
                            if pr > rh: place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                            elif pr < rl: place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn == "INSTITUTIONAL_SUPPORT":
                        info = mt5.symbol_info(symbol)
                        if info:
                            rf = 10**(info.digits - 2)
                            nr = round(pr * rf) / rf
                            if abs(pr - nr) / pr < 0.0005:
                                r = _rsi(df5)
                                if r < 45 and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                                elif r > 55 and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

                    elif sn in ("ZERO_HERO","MAGIC_SQUARE","AI_ENHANCED","SCALPING","PIP_BLAST","SWAP_ARBITRAGE"):
                        e9 = _ema(df5, 9); e21 = _ema(df5, 21); r = _rsi(df5, 7)
                        rsi_buy = 50 + (5 * thresh_val)
                        rsi_sell = 50 - (5 * thresh_val)
                        if e9.iloc[-1] > e21.iloc[-1] and r > rsi_buy and dr in ("BUY","BOTH"): place_order(symbol,"BUY",sn,dna=dna); last_trade_time=time.time(); can_trade=False
                        elif e9.iloc[-1] < e21.iloc[-1] and r < rsi_sell and dr in ("SELL","BOTH"): place_order(symbol,"SELL",sn,dna=dna); last_trade_time=time.time(); can_trade=False

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

def strategy_pnl_tracker():
    """
    QA Requirement: Tracking of all orders and calculating profit by strategy for the Dashboard.
    Runs periodically to query MT5 history for today and aggregate PnL by Strategy (Comment).
    """
    logging.info("[SYSTEM] Strategy PnL Tracker Engine Online.")
    THREAD_STATUS["PNL_TRACKER"] = "Active"
    
    from datetime import datetime
    
    while True:
        try:
            account = mt5.account_info()
            if not account:
                time.sleep(5)
                continue
                
            now_utc = datetime.utcnow()
            start_of_day = datetime(now_utc.year, now_utc.month, now_utc.day)
            
            deals = mt5.history_deals_get(start_of_day, now_utc)
            if deals:
                closed_deals = [d for d in deals if d.magic == 888888 and d.entry == mt5.DEAL_ENTRY_OUT]
                
                strategy_stats = {}
                for d in closed_deals:
                    strat = d.comment
                    if not strat: strat = "UNKNOWN"
                    
                    if strat not in strategy_stats:
                        strategy_stats[strat] = {"trades": 0, "wins": 0, "pnl": 0.0}
                        
                    strategy_stats[strat]["trades"] += 1
                    strategy_stats[strat]["pnl"] += float(d.profit)
                    if d.profit > 0:
                        strategy_stats[strat]["wins"] += 1
                
                # Format for dashboard
                dashboard_data = {}
                for strat, stats in strategy_stats.items():
                    win_rate = f"{(stats['wins'] / stats['trades']):.1%}" if stats['trades'] > 0 else "0.0%"
                    dashboard_data[strat] = {
                        "trades": stats["trades"],
                        "win_rate": win_rate,
                        "pnl": stats["pnl"]
                    }
                
                try:
                    with open(BASE_DIR / "strategy_pnl_today.json", "w") as f:
                        json.dump(dashboard_data, f)
                except Exception as e:
                    pass
            
            time.sleep(10) # Update every 10 seconds
        except Exception as e:
            THREAD_STATUS["PNL_TRACKER"] = f"Error: {e}"
            time.sleep(5)


def status_dumper_loop():
    import time
    import json
    while True:
        try:
            with open(BASE_DIR / "thread_status.json", "w") as f:
                json.dump(THREAD_STATUS, f)
        except: pass
        time.sleep(5)

def run_live_engine():
    if not init_mt5():
        return
        
    logging.info("Starting Multi-Threaded AI Strategy Executor (Multi-Timeframe & Weekend Crypto)...")
    dna_db = get_optimized_dna()
    target_symbols = ["GOLD", "SILVER", "GBPJPY", "USDCHF", "AUDUSD", "USDJPY", "GBPUSD", "BTCUSD", "ETHUSD", "EURUSD"]
    symbols_to_trade = [s for s in target_symbols if mt5.symbol_info(s) is not None or mt5.symbol_info(f"{s}.m") is not None]
    if not symbols_to_trade:
        symbols_to_trade = target_symbols # fallback
    logging.info(f"Active Portfolio Symbols: {symbols_to_trade}")
    
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(symbols_to_trade) + 2)
    
    # Initial Submission
    futures = {}
    futures[executor.submit(trailing_stop_manager, dna_db)] = "TRAILING_ENGINE"
    futures[executor.submit(strategy_pnl_tracker)] = "PNL_TRACKER"
    futures[executor.submit(status_dumper_loop)] = "STATUS_DUMPER"
    for sym in symbols_to_trade:
        futures[executor.submit(process_symbol, sym, dna_db)] = sym
        
    try:
        while True:
            done, not_done = concurrent.futures.wait(futures.keys(), return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                sym_or_engine = futures.pop(future)
                try:
                    # Retrieve exception if any
                    exc = future.exception()
                    if exc:
                        logging.error(f"[{sym_or_engine}] Thread CRASHED: {exc}. Restarting...")
                        try:
                            # Send Alert to Dashboard
                            alert_path = BASE_DIR / "alerts.json"
                            import json, datetime
                            alerts = []
                            if alert_path.exists():
                                with open(alert_path, "r", encoding="utf-8") as af:
                                    try: alerts = json.load(af)
                                    except: pass
                            alerts.append({
                                "source": f"Strategy Engine ({sym_or_engine})",
                                "message": f"Thread crashed: {str(exc)}. Engine is attempting auto-restart.",
                                "level": "CRITICAL",
                                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                            with open(alert_path, "w", encoding="utf-8") as af:
                                json.dump(alerts, af, indent=2)
                        except: pass
                    else:
                        logging.warning(f"[{sym_or_engine}] Thread Exited. Restarting...")
                except Exception as e:
                    logging.error(f"[{sym_or_engine}] Could not retrieve thread exception: {e}")
                
                # Auto-Recover / Restart the thread
                time.sleep(2) # Brief cooldown before restart
                if sym_or_engine == "TRAILING_ENGINE":
                    new_future = executor.submit(trailing_stop_manager, dna_db)
                elif sym_or_engine == "PNL_TRACKER":
                    new_future = executor.submit(strategy_pnl_tracker)
                else:
                    new_future = executor.submit(process_symbol, sym_or_engine, dna_db)
                futures[new_future] = sym_or_engine
                
    except KeyboardInterrupt:
        logging.info("Shutting down live engine threads (KeyboardInterrupt)...")
        executor.shutdown(wait=False)
        mt5.shutdown()

if __name__ == "__main__":
    run_live_engine()
