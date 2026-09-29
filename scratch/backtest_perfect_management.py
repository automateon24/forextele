import json
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
JSON_PATH = BASE_DIR / "perfect_management_scraped.json"

with open(JSON_PATH, "r", encoding="utf-8") as f:
    msgs = json.load(f)

# Load MT5 M1 Gold data
if not mt5.initialize():
    print("MT5 init failed")
    exit(1)

start_dt = datetime(2026, 9, 13, 0, 0, tzinfo=timezone.utc)
end_dt = datetime(2026, 9, 19, 0, 0, tzinfo=timezone.utc)
rates = mt5.copy_rates_range("GOLD", mt5.TIMEFRAME_M1, start_dt, end_dt)
mt5.shutdown()

df_bars = pd.DataFrame(rates)
df_bars['dt'] = pd.to_datetime(df_bars['time'], unit='s', utc=True)
df_bars.sort_values('dt', inplace=True)
print(f"Loaded {len(df_bars)} M1 bars for GOLD.")

# Extract Gold signals
import re
signals = []
for m in msgs:
    text = m['text'].replace('**', ' ').replace('*', ' ').strip()
    sig_m = re.search(r'(?:#)?(XAUUSD|GOLD)\s+(BUY|SELL)\s+([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
    if sig_m:
        act = sig_m.group(2).upper()
        entry = float(sig_m.group(3))
        sl_m = re.search(r'(?:SL|Sl)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)', text)
        sl = float(sl_m.group(1)) if sl_m else (entry - 10 if act == "BUY" else entry + 10)
        tps = re.findall(r'(?:[¹²³⁴⁵⁶1-6]?TP|TP[¹²³⁴⁵⁶1-6]?)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
        tp_list = [float(v) for v in tps]
        if not tp_list:
            tp_list = [entry + 4 if act == "BUY" else entry - 4]
            
        msg_dt = pd.to_datetime(m['date']).to_pydatetime().replace(tzinfo=timezone.utc)
        signals.append({
            "id": m['id'],
            "date": msg_dt,
            "action": act,
            "entry": entry,
            "sl": sl,
            "tp1": tp_list[0],
            "max_tp": tp_list[-1],
            "all_tps": tp_list,
            "raw": text[:80]
        })

print(f"\nSimulating {len(signals)} Gold signals on M1 bars...")

results = []
for s in signals:
    entry_time = s['date']
    act = s['action']
    entry = s['entry']
    sl = s['sl']
    tp1 = s['tp1']
    max_tp = s['max_tp']
    
    sub = df_bars[df_bars['dt'] >= entry_time]
    if len(sub) == 0:
        continue
        
    outcome_tp1 = "OPEN"
    highest_tp_hit = 0
    pnl_pts = 0.0
    
    for idx, bar in sub.iterrows():
        high = bar['high']
        low = bar['low']
        
        # Check SL hit first
        if act == "BUY" and low <= sl:
            outcome_tp1 = "LOSS"
            pnl_pts = sl - entry
            break
        elif act == "SELL" and high >= sl:
            outcome_tp1 = "LOSS"
            pnl_pts = entry - sl
            break
            
        # Check TPs
        if act == "BUY":
            for i, tp in enumerate(s['all_tps']):
                if high >= tp and (i + 1) > highest_tp_hit:
                    highest_tp_hit = i + 1
            if high >= tp1:
                outcome_tp1 = "WIN"
            if high >= max_tp:
                break
        elif act == "SELL":
            for i, tp in enumerate(s['all_tps']):
                if low <= tp and (i + 1) > highest_tp_hit:
                    highest_tp_hit = i + 1
            if low <= tp1:
                outcome_tp1 = "WIN"
            if low <= max_tp:
                break
                
    if outcome_tp1 == "WIN":
        pnl_pts = abs(s['all_tps'][highest_tp_hit - 1] - entry)
        
    pips = round(pnl_pts * 10, 1)
    results.append({
        "id": s['id'],
        "time": entry_time.strftime("%Y-%m-%d %H:%M"),
        "action": act,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "highest_tp_hit": highest_tp_hit,
        "outcome": outcome_tp1,
        "pips": pips
    })

df_res = pd.DataFrame(results)
wins = len(df_res[df_res['outcome'] == 'WIN'])
losses = len(df_res[df_res['outcome'] == 'LOSS'])
tot = len(df_res)
wr = round(wins / tot * 100, 1) if tot > 0 else 0
tot_pips = round(df_res['pips'].sum(), 1)

print("\n--- PERFECT MANAGEMENT BACKTEST RESULTS ---")
print(f"Total Trades: {tot} | Wins: {wins} | Losses: {losses} | Win Rate: {wr}% | Net Pips: {tot_pips}")
print(df_res[["time", "action", "entry", "sl", "highest_tp_hit", "outcome", "pips"]].to_string(index=False))
