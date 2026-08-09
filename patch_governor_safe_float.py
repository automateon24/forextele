import re

with open('swarm_engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

gov_find = """            sl = trade_data.get("sl")
            tp1 = trade_data.get("tp1")
            
            if sl is None or float(sl) <= 0:
                log.info(f"[GOVERNOR] SL missing, auto-calculating ATR proxy for {symbol}")
                sl = entry - atr_sl_dist if "BUY" in action else entry + atr_sl_dist
                
            if tp1 is None or float(tp1) <= 0:
                log.info(f"[GOVERNOR] TP missing, auto-calculating ATR proxy for {symbol}")
                tp1 = entry + atr_tp_dist if "BUY" in action else entry - atr_tp_dist"""

gov_replace = """            sl = trade_data.get("sl")
            tp1 = trade_data.get("tp1")
            
            # Safe float conversion
            try:
                sl_val = float(sl) if sl is not None and sl != "" else 0.0
            except:
                sl_val = 0.0
                
            try:
                tp1_val = float(tp1) if tp1 is not None and tp1 != "" else 0.0
            except:
                tp1_val = 0.0
            
            if sl_val <= 0:
                log.info(f"[GOVERNOR] SL missing or invalid, auto-calculating ATR proxy for {symbol}")
                sl = entry - atr_sl_dist if "BUY" in action else entry + atr_sl_dist
            else:
                sl = sl_val
                
            if tp1_val <= 0:
                log.info(f"[GOVERNOR] TP missing or invalid, auto-calculating ATR proxy for {symbol}")
                tp1 = entry + atr_tp_dist if "BUY" in action else entry - atr_tp_dist
            else:
                tp1 = tp1_val"""

code = code.replace(gov_find, gov_replace)

with open('swarm_engine.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched swarm_engine.py to safely handle ValueError on float conversions!")
