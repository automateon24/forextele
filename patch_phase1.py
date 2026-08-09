import re

with open('live_strategy_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add joblib import and load model globally
import_str = "import joblib\n\nBASE_DIR"
code = code.replace("BASE_DIR", import_str, 1)

model_load_str = '''
ML_MODEL_PATH = BASE_DIR / "final_model_sucess.joblib"
try:
    ML_MODEL = joblib.load(ML_MODEL_PATH)
    logging.info(f"Successfully loaded ML Model: {ML_MODEL_PATH}")
except Exception as e:
    logging.error(f"Failed to load ML Model: {e}")
    ML_MODEL = None
'''
code = code.replace("DNA_PATH = BASE_DIR / \"25stragy\" / \"ai_optimized_forex_dna.json\"\n", "DNA_PATH = BASE_DIR / \"25stragy\" / \"ai_optimized_forex_dna.json\"\n" + model_load_str)


# Modify place_order
place_order_def = "def place_order(symbol, trade_type, strat_name, dna=None, magic_number=888888):"
new_place_order = '''def place_order(symbol, trade_type, strat_name, dna=None, magic_number=888888):
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
    
    # ── Phase 1: Golden Hours Dual-Zone R/R ──
    utc_now = datetime.utcnow()
    utc_h = utc_now.hour
    weekday = utc_now.weekday()
    
    sl_atr_mult = 1.5
    tp_atr_mult = 3.0
    
    if dna is not None:
        sl_atr_mult = max(float(dna.get("sl", 1.5)), 0.1)
        golden_hours = dna.get("golden_hours", [])
        if golden_hours and utc_h in golden_hours:
            tp_atr_mult = max(float(dna.get("golden_rr", 3.0)), 0.2)
            logging.info(f"[{symbol}] Trade in Golden Hour ({utc_h} UTC). Targeting {tp_atr_mult} R:R.")
        else:
            tp_atr_mult = max(float(dna.get("fallback_rr", 2.0)), 0.2)
            logging.info(f"[{symbol}] Trade outside Golden Hour ({utc_h} UTC). Targeting reduced {tp_atr_mult} R:R.")

    if atr > 0:
        sl_points_raw = atr * sl_atr_mult
        tp_points_raw = atr * tp_atr_mult
    else:
        pip_mult = 10 if digits in [3, 5] else 1
        sl_points_raw = 50 * pip_mult * point
        tp_points_raw = 100 * pip_mult * point
        
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
                
            import pandas as pd
            feature_dict = {
                "symbol": symbol,
                "strategy": strat_name,
                "direction": trade_type,
                "session": session,
                "hour": utc_h,
                "weekday": weekday,
                "rsi_val": rsi_val,
                "adx_val": adx_val,
                "atr": sl_points_raw, # We fed sl_points_raw / point in backtest, but ATR in backtest was just the pip amount. Wait! Let's just give it raw ATR.
                "sl_pts": sl_points_count,
                "tp_pts": tp_points_count
            }
            
            # Need to match backtest atr definition: backtest atr feature was `s['atr'] / point`.
            feature_dict["atr"] = atr / point if point > 0 else 0
            
            df_features = pd.DataFrame([feature_dict])
            prob = ML_MODEL.predict_proba(df_features)[0][1]
            
            if prob < 0.50:
                logging.info(f"[{symbol}] ML FILTERED TRADE: {strat_name} | {trade_type} | Win Prob: {prob:.1%} < 50%.")
                return None
            else:
                logging.info(f"[{symbol}] ML APPROVED: {strat_name} | {trade_type} | Win Prob: {prob:.1%} >= 50%.")
                
        except Exception as ml_err:
            logging.error(f"[{symbol}] ML Inference Error: {ml_err}. Proceeding without ML.")
'''

# Find place_order function boundaries
start_idx = code.find(place_order_def)
# Find the end of place_order function
end_idx = code.find("def trailing_stop_manager", start_idx)

# Replace the old place_order body with the new logic, but keeping the actual execution part at the end
# Actually, it's easier to just reconstruct the execution part as well.

new_place_order_full = new_place_order + '''
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
'''

code = code[:start_idx] + new_place_order_full + "\n" + code[end_idx:]

with open('live_strategy_executor.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Patched live_strategy_executor.py for Phase 1!")
