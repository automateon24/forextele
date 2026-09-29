import re

def parse_pm_signal(clean: str):
    clean = clean.replace('**', ' ').replace('*', ' ').strip()
    
    # 1. Match symbol, action, entry
    sig_match = re.search(r'(?:#)?(XAUUSD|GOLD|BTCUSD|BTC|ETHUSD|ETH|US30|EURUSD|GBPUSD|USDJPY|GBPJPY|AUDUSD)\s+(BUY|SELL)\s+([0-9]+(?:\.[0-9]+)?)', clean, re.IGNORECASE)
    if not sig_match:
        return {"status": "NOT_MATCHED"}
        
    raw_sym = sig_match.group(1).upper()
    action = sig_match.group(2).upper()
    entry = float(sig_match.group(3))
    
    symbol = "GOLD" if raw_sym in ("XAUUSD", "GOLD") else ("BTCUSD" if raw_sym == "BTC" else raw_sym)
    
    # 2. Stop Loss (support SL, Sl, SI, Si, Stop Loss)
    sl_m = re.search(r'(?:SL|Sl|SI|Si|Stop\s*Loss)\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)', clean, re.IGNORECASE)
    sl_price = float(sl_m.group(1)) if sl_m else None
    
    # 3. Multi-TPs
    # Distinctly match prefix digit (1TP), postfix digit (TP1), superscript (¹TP), or plain (TP)
    # Never let the index consume the first digit of the price!
    tp_pattern = r'(?:[¹²³⁴⁵⁶1-6]TP|TP[¹²³⁴⁵⁶1-6]|TARGET\s*[1-6]|TP)\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)'
    tp_matches = re.findall(tp_pattern, clean, re.IGNORECASE)
    tp_list = [float(v) for v in tp_matches]
    
    # Deduplicate while preserving order
    seen = set()
    dedup_tps = []
    for t in tp_list:
        if t not in seen:
            seen.add(t)
            dedup_tps.append(t)
            
    # Sort logically
    if action == "BUY":
        dedup_tps = sorted(dedup_tps)
    else:
        dedup_tps = sorted(dedup_tps, reverse=True)
        
    return {
        "status": "PARSED",
        "raw_sym": raw_sym,
        "symbol": symbol,
        "action": action,
        "entry": entry,
        "sl": sl_price,
        "tps": dedup_tps,
        "tp1": dedup_tps[0] if dedup_tps else None,
        "max_tp": dedup_tps[-1] if dedup_tps else None
    }

msg1 = """BTCUSD SELL 81320

SL 81620

TP 81220
TP 81120
TP 81020
TP 80920
TP 80820
TP 80720"""

msg2 = """#XAUUSD BUY 4352

SI 4342

1TP 4356
2TP 4360
3TP 4364
4TP 4368
5TP 4372
6TP 4376"""

msg3 = """#XAUUSD SELL 4383 SI 4394 1TP 4379 2TP 4375 3TP 4371 4TP 4367 5TP 4363 6TP 4359"""

msg4 = """#XAUUSD BUY 4352
SI 4342
¹TP 4356
²TP 4360
³TP 4364
⁴TP 4368
⁵TP 4372
⁶TP 4376"""

for i, m in enumerate([msg1, msg2, msg3, msg4], 1):
    res = parse_pm_signal(m)
    print(f"--- Test Case {i} ---")
    print(res)
