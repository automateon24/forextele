import re

with open('live_strategy_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Modify place_order for Phase 3 (Spread Protection)
find_str = """    info = mt5.symbol_info(symbol)
    point = info.point
    digits = info.digits"""

replace_str = """    info = mt5.symbol_info(symbol)
    point = info.point
    digits = info.digits
    
    # ── Phase 3: Live Spread Protection ──
    spread = info.spread
    max_spread = 20  # Fallback
    if "USD" in symbol or "JPY" in symbol:
        if symbol == "BTCUSD": max_spread = 500
        elif symbol == "ETHUSD": max_spread = 200
        elif symbol in ("GOLD", "XAUUSD"): max_spread = 50
        elif symbol in ("SILVER", "XAGUSD"): max_spread = 40
        else: max_spread = 15 # Forex standard limit
    
    if spread > max_spread:
        logging.warning(f"[{symbol}] 🚨 Spread Protection: Live Spread ({spread}) > Max Allowable ({max_spread}). Trade Aborted.")
        return None
"""

code = code.replace(find_str, replace_str)

with open('live_strategy_executor.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Patched live_strategy_executor.py for Phase 3!")
