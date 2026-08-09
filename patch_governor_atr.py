import re

with open('swarm_engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

gov_find = """        if entry is None or float(entry) <= 0:
            risk_decision = {"approved": False, "rejection_reason": "No entry price provided"}
        elif sl is None or float(sl) <= 0:
            risk_decision = {"approved": False, "rejection_reason": "No Stop Loss provided"}
        else:
            risk_decision = {
                "approved": True,
                "rejection_reason": "",
                "final_sl": sl,
                "final_tp1": tp1,
                "final_tp2": trade_data.get("tp2"),
                "final_tp3": trade_data.get("tp3"),
                "risk_reward_ratio": 1.5
            }"""

gov_replace = """        if entry is None or float(entry) <= 0:
            risk_decision = {"approved": False, "rejection_reason": "No entry price provided"}
        else:
            entry = float(entry)
            symbol = trade_data.get("symbol", "").upper()
            action = trade_data.get("action", "BUY").upper()
            
            # Default ATR proxies if missing
            is_gold = "XAU" in symbol or "GOLD" in symbol
            atr_sl_dist = 10.0 if is_gold else 0.0050
            atr_tp_dist = 20.0 if is_gold else 0.0100
            
            sl = trade_data.get("sl")
            tp1 = trade_data.get("tp1")
            
            if sl is None or float(sl) <= 0:
                log.info(f"[GOVERNOR] SL missing, auto-calculating ATR proxy for {symbol}")
                sl = entry - atr_sl_dist if "BUY" in action else entry + atr_sl_dist
                
            if tp1 is None or float(tp1) <= 0:
                log.info(f"[GOVERNOR] TP missing, auto-calculating ATR proxy for {symbol}")
                tp1 = entry + atr_tp_dist if "BUY" in action else entry - atr_tp_dist
                
            risk_decision = {
                "approved": True,
                "rejection_reason": "",
                "final_sl": float(sl),
                "final_tp1": float(tp1),
                "final_tp2": trade_data.get("tp2"),
                "final_tp3": trade_data.get("tp3"),
                "risk_reward_ratio": 1.5
            }"""

code = code.replace(gov_find, gov_replace)

with open('swarm_engine.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched swarm_engine.py with ATR SL/TP logic!")
