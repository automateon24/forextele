import json
import re
from pathlib import Path

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
with open(BASE_DIR / "perfect_management_scraped.json", "r", encoding="utf-8") as f:
    msgs = json.load(f)

# Sort chronologically
msgs.sort(key=lambda x: x['date'])

signals = []
for m in msgs:
    text = m['text'].replace('**', ' ').replace('*', ' ').strip()
    
    # Pattern for Perfect Management signal:
    # #XAUUSD BUY 4352 \n Sl 4342 \n 1TP 4356 ...
    # or BTCUSD SELL 81320 \n SL 81620 \n TP 81220 ...
    sig_match = re.search(r'(?:#)?(XAUUSD|GOLD|BTCUSD|ETHUSD)\s+(BUY|SELL)\s+([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
    if sig_match:
        sym = sig_match.group(1).upper()
        act = sig_match.group(2).upper()
        entry = float(sig_match.group(3))
        
        sl_m = re.search(r'(?:SL|Sl)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)', text)
        sl = float(sl_m.group(1)) if sl_m else None
        
        tps = re.findall(r'(?:[¹²³⁴⁵⁶1-6]?TP|TP[¹²³⁴⁵⁶1-6]?)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
        tp_list = [float(v) for v in tps]
        
        signals.append({
            "id": m['id'],
            "date": m['date'],
            "symbol": sym,
            "action": act,
            "entry": entry,
            "sl": sl,
            "tps": tp_list,
            "raw": text
        })

print(f"Total actionable signals extracted: {len(signals)}")
for s in signals:
    print(f"[{s['date']}] ID {s['id']}: {s['action']} {s['symbol']} @ {s['entry']} | SL: {s['sl']} | TPs: {s['tps']}")
