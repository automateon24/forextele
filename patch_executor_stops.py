import re

with open('live_strategy_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

find_block = """    if atr > 0:
        sl_points_raw = atr * sl_atr_mult
        tp_points_raw = atr * tp_atr_mult
    else:
        pip_mult = 10 if digits in [3, 5] else 1
        sl_points_raw = 50 * pip_mult * point
        tp_points_raw = 100 * pip_mult * point
        
    sl_points_count = sl_points_raw / point if point > 0 else 1000
    tp_points_count = tp_points_raw / point if point > 0 else 2000"""

replace_block = """    if atr > 0:
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
    
    sl_points_raw = max(sl_points_raw, min_dist * 1.5, hard_min)
    tp_points_raw = max(tp_points_raw, min_dist * 2.0, hard_min * 2)
        
    sl_points_count = sl_points_raw / point if point > 0 else 1000
    tp_points_count = tp_points_raw / point if point > 0 else 2000"""

code = code.replace(find_block, replace_block)

# Also add fallback retry logic around `order_send`
find_send = """    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"[{symbol}] Order Failed! Code: {result.retcode} Comment: {result.comment}")
        return None"""

replace_send = """    result = mt5.order_send(request)
    if result.retcode == 10016:
        logging.warning(f"[{symbol}] Retcode 10016 (Invalid Stops). Retrying with widened safety stops...")
        request["sl"] = round(price - (sl_points_raw * 1.5) if action == mt5.ORDER_TYPE_BUY else price + (sl_points_raw * 1.5), digits)
        request["tp"] = round(price + (tp_points_raw * 1.5) if action == mt5.ORDER_TYPE_BUY else price - (tp_points_raw * 1.5), digits)
        result = mt5.order_send(request)
        
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"[{symbol}] Order Failed! Code: {result.retcode} Comment: {result.comment}")
        return None"""

code = code.replace(find_send, replace_send)

with open('live_strategy_executor.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched live_strategy_executor.py for Invalid Stops")
