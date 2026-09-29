"""
BACKTEST: PURE FIXED SL & TP (ZERO TSL) VS TSL MODES
====================================================
Evaluates all 3-day Telegram signals (Sep 21 00:00 UTC to Sep 23 13:00 UTC)
Testing pure hold to original SL and TPs with ZERO trailing stop loss.

Modes Tested:
  1. Pure Fixed SL to TP1 (No TSL)
  2. Pure Fixed SL to TP2 (No TSL)
  3. Pure Fixed SL to TP3 (No TSL, Full Runner)
  4. Hybrid Fixed: 50% TP1, 50% TP2 (Original SL untouched throughout)
  5. Comparison with Mode A (Premature TSL) and Mode B (Breathing TSL)
"""
import csv
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
SCRATCH_DIR = BASE_DIR / "scratch"

if not mt5.initialize():
    print("MT5 initialization failed!")
    exit(1)

M1_CACHE = {}

def get_m1_data(symbol):
    if symbol in M1_CACHE:
        return M1_CACHE[symbol]
    mt5.symbol_select(symbol, True)
    start = datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, now)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('datetime', inplace=True)
    M1_CACHE[symbol] = df
    return df

def get_pip_size(symbol):
    if symbol == "GOLD": return 0.10
    if symbol == "BTCUSD": return 1.0
    if "JPY" in symbol: return 0.01
    if symbol == "US30Cash": return 1.0
    return 0.0001

def calc_pnl_usd(symbol, pnl_pips):
    if symbol == "GOLD": return pnl_pips * 0.10
    if symbol == "BTCUSD": return pnl_pips * 0.01
    if "JPY" in symbol: return pnl_pips * 0.065
    if symbol == "US30Cash": return pnl_pips * 0.01
    return pnl_pips * 0.085

# Collect signals from signals_audit.csv and full_telegram_scrape_today.json
print("Loading all scraped signals from the past 3 days...")
all_signals = []
seen_signatures = set()
from_time = datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc)

# 1. From signals_audit.csv
audit_file = BASE_DIR / "signals_audit.csv"
if audit_file.exists():
    with open(audit_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 7: continue
            try:
                dt = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception: continue
            if dt < from_time: continue

            channel = row[2]
            action = row[5] if len(row) >= 11 else ""
            symbol = row[6] if len(row) >= 11 else ""
            entry_str = row[7] if len(row) >= 11 else ""
            sl_str = row[8] if len(row) >= 11 else ""
            tp_str = row[9] if len(row) >= 11 else ""
            raw_msg = row[3] if len(row) > 3 else ""

            if not action or action not in ("BUY", "SELL"):
                parsed_col = row[4] if len(row) > 4 else ""
                m = re.search(r'\b(BUY|SELL)\s+([A-Za-z0-9]+)\s+@\s*([0-9.]+)', parsed_col)
                if m:
                    action, symbol, entry_str = m.group(1).upper(), m.group(2).upper(), m.group(3)
                else: continue

            try:
                entry = float(entry_str) if entry_str else 0.0
                sl = float(sl_str) if sl_str else 0.0
                tp = float(tp_str) if tp_str else 0.0
            except ValueError: continue

            sym = "GOLD" if symbol in ("XAUUSD", "GOLD") else ("BTCUSD" if "BTC" in symbol else ("US30Cash" if "US30" in symbol else symbol))
            sig_id = f"{channel}_{sym}_{action}_{entry}_{dt.strftime('%Y%m%d%H%M')}"
            if sig_id not in seen_signatures:
                seen_signatures.add(sig_id)
                all_signals.append({
                    "timestamp": dt, "channel": channel, "symbol": sym, "action": action,
                    "entry": entry, "sl": sl, "tps": [tp] if tp > 0 else [], "raw_msg": raw_msg[:120]
                })

# 2. From full_telegram_scrape_today.json
scrape_json = SCRATCH_DIR / "full_telegram_scrape_today.json"
if scrape_json.exists():
    try:
        scrape_data = json.load(open(scrape_json, encoding="utf-8"))
        for ch_name, cdata in scrape_data.get("channels", {}).items():
            for sig_item in cdata.get("signals", []):
                t_str = sig_item.get("time", "")
                try:
                    dt = datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                except Exception: continue
                if dt < from_time: continue
                s = sig_item.get("signal", {})
                action = s.get("action", "").upper()
                symbols = s.get("symbols", [])
                sym = "GOLD" if (symbols and symbols[0] in ("XAUUSD", "GOLD")) else (symbols[0] if symbols else "GOLD")
                entry = s.get("entry") or 0.0
                sl = s.get("sl") or 0.0
                tps = s.get("tps") or []

                sig_id = f"{ch_name}_{sym}_{action}_{entry}_{dt.strftime('%Y%m%d%H%M')}"
                if sig_id not in seen_signatures:
                    seen_signatures.add(sig_id)
                    all_signals.append({
                        "timestamp": dt, "channel": ch_name, "symbol": sym, "action": action,
                        "entry": entry, "sl": sl, "tps": tps, "raw_msg": sig_item.get("text", "")[:120]
                    })
    except Exception as e:
        print(f"Scrape json error: {e}")

print(f"Total Unique Valid Signals: {len(all_signals)}")

# Simulation function for Pure Fixed SL / TP (NO TSL)
def simulate_pure_fixed(sig):
    sym = sig["symbol"]
    action = sig["action"]
    sig_time = sig["timestamp"]
    stated_entry = sig["entry"]
    stated_sl = sig["sl"]
    stated_tps = sig["tps"]

    df = get_m1_data(sym)
    if df is None or len(df) == 0: return None

    df_after = df.loc[df.index >= sig_time]
    if len(df_after) < 5: return None

    pip_size = get_pip_size(sym)
    market_open = df_after['open'].iloc[0]

    if stated_entry and abs(stated_entry - market_open) <= (30 * pip_size):
        entry_price = stated_entry
    else:
        entry_price = market_open

    default_sl_dist = 40 * pip_size if sym == "GOLD" else 35 * pip_size
    if stated_sl and ((action == "BUY" and stated_sl < entry_price) or (action == "SELL" and stated_sl > entry_price)):
        original_sl = stated_sl
    else:
        original_sl = entry_price - default_sl_dist if action == "BUY" else entry_price + default_sl_dist

    valid_tps = []
    for tp in stated_tps:
        if (action == "BUY" and tp > entry_price) or (action == "SELL" and tp < entry_price):
            valid_tps.append(tp)
    if not valid_tps:
        tp1_dist = 30 * pip_size if sym == "GOLD" else 25 * pip_size
        tp2_dist = 70 * pip_size if sym == "GOLD" else 60 * pip_size
        tp3_dist = 120 * pip_size if sym == "GOLD" else 100 * pip_size
        valid_tps = [
            entry_price + tp1_dist if action == "BUY" else entry_price - tp1_dist,
            entry_price + tp2_dist if action == "BUY" else entry_price - tp2_dist,
            entry_price + tp3_dist if action == "BUY" else entry_price - tp3_dist,
        ]
    else:
        valid_tps = sorted(valid_tps) if action == "BUY" else sorted(valid_tps, reverse=True)

    tp1 = valid_tps[0]
    tp2 = valid_tps[1] if len(valid_tps) > 1 else (entry_price + 2 * abs(tp1 - entry_price) if action == "BUY" else entry_price - 2 * abs(tp1 - entry_price))
    tp3 = valid_tps[2] if len(valid_tps) > 2 else (entry_price + 3 * abs(tp1 - entry_price) if action == "BUY" else entry_price - 3 * abs(tp1 - entry_price))

    spread_cost = 0.53 if sym == "GOLD" else 0.25

    # ── Simulation 1: Pure Fixed SL to TP1 (Zero TSL) ──
    # SL never moves from original_sl. Trade exits at TP1 or original_sl.
    exit_p1 = entry_price
    outcome_p1 = "OPEN"
    for idx, (bar_time, row) in enumerate(df_after.iterrows()):
        high, low = row['high'], row['low']
        if action == "BUY":
            if low <= original_sl:
                exit_p1 = original_sl
                outcome_p1 = "LOSS_SL"
                break
            if high >= tp1:
                exit_p1 = tp1
                outcome_p1 = "WIN_TP1"
                break
        else: # SELL
            if high >= original_sl:
                exit_p1 = original_sl
                outcome_p1 = "LOSS_SL"
                break
            if low <= tp1:
                exit_p1 = tp1
                outcome_p1 = "WIN_TP1"
                break
    pnl_dist_1 = (exit_p1 - entry_price) if action == "BUY" else (entry_price - exit_p1)
    pnl_usd_tp1 = calc_pnl_usd(sym, pnl_dist_1 / pip_size) - spread_cost

    # ── Simulation 2: Pure Fixed SL to TP2 (Zero TSL) ──
    # SL never moves from original_sl. Trade exits at TP2 or original_sl.
    exit_p2 = entry_price
    outcome_p2 = "OPEN"
    for idx, (bar_time, row) in enumerate(df_after.iterrows()):
        high, low = row['high'], row['low']
        if action == "BUY":
            if low <= original_sl:
                exit_p2 = original_sl
                outcome_p2 = "LOSS_SL"
                break
            if high >= tp2:
                exit_p2 = tp2
                outcome_p2 = "WIN_TP2"
                break
        else:
            if high >= original_sl:
                exit_p2 = original_sl
                outcome_p2 = "LOSS_SL"
                break
            if low <= tp2:
                exit_p2 = tp2
                outcome_p2 = "WIN_TP2"
                break
    pnl_dist_2 = (exit_p2 - entry_price) if action == "BUY" else (entry_price - exit_p2)
    pnl_usd_tp2 = calc_pnl_usd(sym, pnl_dist_2 / pip_size) - spread_cost

    # ── Simulation 3: Pure Fixed SL to TP3 (Zero TSL, Full Runner) ──
    exit_p3 = entry_price
    outcome_p3 = "OPEN"
    for idx, (bar_time, row) in enumerate(df_after.iterrows()):
        high, low = row['high'], row['low']
        if action == "BUY":
            if low <= original_sl:
                exit_p3 = original_sl
                outcome_p3 = "LOSS_SL"
                break
            if high >= tp3:
                exit_p3 = tp3
                outcome_p3 = "WIN_TP3"
                break
        else:
            if high >= original_sl:
                exit_p3 = original_sl
                outcome_p3 = "LOSS_SL"
                break
            if low <= tp3:
                exit_p3 = tp3
                outcome_p3 = "WIN_TP3"
                break
    pnl_dist_3 = (exit_p3 - entry_price) if action == "BUY" else (entry_price - exit_p3)
    pnl_usd_tp3 = calc_pnl_usd(sym, pnl_dist_3 / pip_size) - spread_cost

    # ── Simulation 4: Hybrid Fixed: 50% TP1, 50% TP2 with Original SL (Zero TSL) ──
    # Half volume closes at TP1, other half closes at TP2, SL stays at original SL throughout!
    pnl_usd_hybrid = round(0.5 * pnl_usd_tp1 + 0.5 * pnl_usd_tp2, 2)
    outcome_hybrid = "WIN" if pnl_usd_hybrid > 0 else "LOSS"

    # ── Also calculate Mode A (Premature TSL) for direct side-by-side comparison ──
    be_threshold = 20.0 * pip_size
    be_sl = entry_price + (0.25 if sym == "GOLD" else 2.0 * pip_size) if action == "BUY" else entry_price - (0.25 if sym == "GOLD" else 2.0 * pip_size)
    sl_a = original_sl
    exit_a = entry_price
    hit_be_a = False
    outcome_a = "OPEN"
    for idx, (bar_time, row) in enumerate(df_after.iterrows()):
        high, low = row['high'], row['low']
        if action == "BUY":
            if not hit_be_a and (high - entry_price) >= be_threshold:
                hit_be_a, sl_a = True, be_sl
            if low <= sl_a:
                exit_a, outcome_a = sl_a, ("BREAKEVEN" if hit_be_a else "LOSS_SL")
                break
            if high >= tp3:
                exit_a, outcome_a = tp3, "WIN_TP3"
                break
        else:
            if not hit_be_a and (entry_price - low) >= be_threshold:
                hit_be_a, sl_a = True, be_sl
            if high >= sl_a:
                exit_a, outcome_a = sl_a, ("BREAKEVEN" if hit_be_a else "LOSS_SL")
                break
            if low <= tp3:
                exit_a, outcome_a = tp3, "WIN_TP3"
                break
    pnl_dist_a = (exit_a - entry_price) if action == "BUY" else (entry_price - exit_a)
    pnl_usd_mode_a = calc_pnl_usd(sym, pnl_dist_a / pip_size) - spread_cost

    return {
        "channel": sig["channel"],
        "symbol": sym,
        "action": action,
        "timestamp": sig_time.strftime("%Y-%m-%d %H:%M"),
        "entry": round(entry_price, 2),
        "sl": round(original_sl, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "tp3": round(tp3, 2),
        # Results
        "pnl_pure_tp1": round(pnl_usd_tp1, 2),
        "outcome_tp1": outcome_p1,
        "pnl_pure_tp2": round(pnl_usd_tp2, 2),
        "outcome_tp2": outcome_p2,
        "pnl_pure_tp3": round(pnl_usd_tp3, 2),
        "outcome_tp3": outcome_p3,
        "pnl_hybrid_50_50": pnl_usd_hybrid,
        "outcome_hybrid": outcome_hybrid,
        "pnl_mode_a_tsl": round(pnl_usd_mode_a, 2),
        "outcome_mode_a": outcome_a
    }

print("Running pure fixed SL simulations across all setups...")
results = []
for sig in all_signals:
    res = simulate_pure_fixed(sig)
    if res:
        results.append(res)

print(f"Simulations Completed: {len(results)} trade setups evaluated")

# Aggregations
n = len(results)

# 1. Mode A (Premature TSL - What was running live)
wins_a = sum(1 for r in results if r["pnl_mode_a_tsl"] > 0)
be_a = sum(1 for r in results if r["outcome_mode_a"] == "BREAKEVEN")
net_a = sum(r["pnl_mode_a_tsl"] for r in results)

# 2. Pure Fixed SL / TP1 (Zero TSL)
wins_tp1 = sum(1 for r in results if r["outcome_tp1"] == "WIN_TP1")
net_tp1 = sum(r["pnl_pure_tp1"] for r in results)

# 3. Pure Fixed SL / TP2 (Zero TSL)
wins_tp2 = sum(1 for r in results if r["outcome_tp2"] == "WIN_TP2")
net_tp2 = sum(r["pnl_pure_tp2"] for r in results)

# 4. Pure Fixed SL / TP3 (Zero TSL, Full Runner)
wins_tp3 = sum(1 for r in results if r["outcome_tp3"] == "WIN_TP3")
net_tp3 = sum(r["pnl_pure_tp3"] for r in results)

# 5. Hybrid 50/50 (50% TP1, 50% TP2, Zero TSL)
wins_hyb = sum(1 for r in results if r["outcome_hybrid"] == "WIN")
net_hyb = sum(r["pnl_hybrid_50_50"] for r in results)

print("\n" + "=" * 85)
print("  EMPIRICAL AUDIT: PURE FIXED SL & TP (ZERO TSL) VS PREMATURE TSL")
print("=" * 85)
print(f"Total Setups Tested: {n}")

print(f"\n1. PREMATURE TSL (Mode A / Old Live System):")
print(f"   Wins: {wins_a} | Breakevens: {be_a} | Losses: {n - wins_a - be_a}")
print(f"   Win Rate: {wins_a/n*100:.1f}%")
print(f"   Net USD: ${net_a:.2f}")

print(f"\n2. PURE FIXED SL / TARGET 1 (ZERO TSL):")
print(f"   Wins: {wins_tp1} | Losses: {n - wins_tp1}")
print(f"   Win Rate: {wins_tp1/n*100:.1f}%")
print(f"   Net USD: ${net_tp1:.2f}")
print(f"   Improvement vs Premature TSL: +${net_tp1 - net_a:.2f}")

print(f"\n3. PURE FIXED SL / TARGET 2 (ZERO TSL):")
print(f"   Wins: {wins_tp2} | Losses: {n - wins_tp2}")
print(f"   Win Rate: {wins_tp2/n*100:.1f}%")
print(f"   Net USD: ${net_tp2:.2f}")
print(f"   Improvement vs Premature TSL: +${net_tp2 - net_a:.2f}")

print(f"\n4. PURE FIXED SL / TARGET 3 (ZERO TSL, MACRO RUNNERS):")
print(f"   Wins: {wins_tp3} | Losses: {n - wins_tp3}")
print(f"   Win Rate: {wins_tp3/n*100:.1f}%")
print(f"   Net USD: ${net_tp3:.2f}")
print(f"   Improvement vs Premature TSL: +${net_tp3 - net_a:.2f}")

print(f"\n5. HYBRID FIXED (50% TP1 + 50% TP2, ZERO TSL):")
print(f"   Wins: {wins_hyb} | Losses: {n - wins_hyb}")
print(f"   Win Rate: {wins_hyb/n*100:.1f}%")
print(f"   Net USD: ${net_hyb:.2f}")
print(f"   Improvement vs Premature TSL: +${net_hyb - net_a:.2f}")

# Channel by channel breakdown under Pure Fixed SL to TP1 vs TP2 vs Premature TSL
ch_perf = defaultdict(lambda: {"trades": 0, "net_tsl": 0.0, "net_tp1": 0.0, "net_tp2": 0.0, "net_tp3": 0.0, "net_hyb": 0.0})
for r in results:
    ch = r["channel"]
    ch_perf[ch]["trades"] += 1
    ch_perf[ch]["net_tsl"] += r["pnl_mode_a_tsl"]
    ch_perf[ch]["net_tp1"] += r["pnl_pure_tp1"]
    ch_perf[ch]["net_tp2"] += r["pnl_pure_tp2"]
    ch_perf[ch]["net_tp3"] += r["pnl_pure_tp3"]
    ch_perf[ch]["net_hyb"] += r["pnl_hybrid_50_50"]

print("\n" + "=" * 95)
print(f"{'Channel':<33} | {'Trades':>6} | {'Premature TSL':>13} | {'Fixed TP1':>10} | {'Fixed TP2':>10} | {'Hybrid 50/50':>12}")
print("-" * 95)
for k, v in sorted(ch_perf.items(), key=lambda x: x[1]["net_tp1"], reverse=True)[:25]:
    ch_c = k.encode('ascii', 'ignore').decode('ascii').strip()
    print(f"{ch_c[:32]:<33} | {v['trades']:>6} | ${v['net_tsl']:>12.2f} | ${v['net_tp1']:>9.2f} | ${v['net_tp2']:>9.2f} | ${v['net_hyb']:>11.2f}")

# Save detailed report
out_summary = {
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "period": "Last 3 Days (Sep 21 00:00 UTC to Sep 23 13:00 UTC)",
    "total_setups": n,
    "modes_summary": {
        "premature_tsl": {"wins": wins_a, "breakevens": be_a, "win_rate": round(wins_a/n*100, 1), "net_usd": round(net_a, 2)},
        "pure_fixed_tp1": {"wins": wins_tp1, "win_rate": round(wins_tp1/n*100, 1), "net_usd": round(net_tp1, 2), "gain_vs_tsl": round(net_tp1 - net_a, 2)},
        "pure_fixed_tp2": {"wins": wins_tp2, "win_rate": round(wins_tp2/n*100, 1), "net_usd": round(net_tp2, 2), "gain_vs_tsl": round(net_tp2 - net_a, 2)},
        "pure_fixed_tp3": {"wins": wins_tp3, "win_rate": round(wins_tp3/n*100, 1), "net_usd": round(net_tp3, 2), "gain_vs_tsl": round(net_tp3 - net_a, 2)},
        "hybrid_50_50": {"wins": wins_hyb, "win_rate": round(wins_hyb/n*100, 1), "net_usd": round(net_hyb, 2), "gain_vs_tsl": round(net_hyb - net_a, 2)},
    },
    "channels": {k: {sk: (round(sv, 2) if isinstance(sv, float) else sv) for sk, sv in v.items()} for k, v in ch_perf.items()}
}

json_path = SCRATCH_DIR / "pure_fixed_sl_no_tsl_results.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(out_summary, f, indent=2, default=str)

print(f"\nDetailed JSON saved to: {json_path}")
mt5.shutdown()
