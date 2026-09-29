"""
SCRAPE 3 DAYS & COMPARATIVE BACKTEST: PREMATURE TSL VS EXTENDED HOLD
=====================================================================
Analyzes all Telegram signals from Sep 21 00:00 UTC to Sep 23 13:00 UTC (last 3 days)
Compares:
  1. Live Actual MT5 Deals (what really happened with premature TSL)
  2. Mode A: Aggressive TSL (move to breakeven after +$2 / TP1)
  3. Mode B: Extended Hold / Breathing Room (proper ATR breathing room, hold for TP2/TP3)
"""
import asyncio
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

# 1. Initialize MT5
if not mt5.initialize():
    print("Failed to initialize MT5!")
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

# 2. Collect All Signals from the Last 3 Days
# Combine signals_audit.csv and full_telegram_scrape_today.json
print("Collecting signals from last 3 days (Sep 21 00:00 UTC to now)...")

all_signals = []
seen_signatures = set()

# A. From signals_audit.csv
audit_file = BASE_DIR / "signals_audit.csv"
from_time = datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc)

if audit_file.exists():
    with open(audit_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 7:
                continue
            ts_str = row[0]
            try:
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if dt < from_time:
                continue

            channel = row[2]
            action = row[5] if len(row) >= 11 else ""
            symbol = row[6] if len(row) >= 11 else ""
            entry_str = row[7] if len(row) >= 11 else ""
            sl_str = row[8] if len(row) >= 11 else ""
            tp_str = row[9] if len(row) >= 11 else ""
            raw_msg = row[3] if len(row) > 3 else ""

            if not action or action not in ("BUY", "SELL"):
                # Try parsing parsed_signal or raw_msg
                parsed_col = row[4] if len(row) > 4 else ""
                m = re.search(r'\b(BUY|SELL)\s+([A-Za-z0-9]+)\s+@\s*([0-9.]+)', parsed_col)
                if m:
                    action = m.group(1).upper()
                    symbol = m.group(2).upper()
                    entry_str = m.group(3)
                else:
                    continue

            try:
                entry = float(entry_str) if entry_str else 0.0
                sl = float(sl_str) if sl_str else 0.0
                tp = float(tp_str) if tp_str else 0.0
            except ValueError:
                continue

            if symbol in ("XAUUSD", "GOLD"):
                sym = "GOLD"
            elif "BTC" in symbol:
                sym = "BTCUSD"
            elif "US30" in symbol:
                sym = "US30Cash"
            else:
                sym = symbol

            sig_id = f"{channel}_{sym}_{action}_{entry}_{dt.strftime('%Y%m%d%H%M')}"
            if sig_id not in seen_signatures:
                seen_signatures.add(sig_id)
                all_signals.append({
                    "timestamp": dt,
                    "channel": channel,
                    "symbol": sym,
                    "action": action,
                    "entry": entry,
                    "sl": sl,
                    "tps": [tp] if tp > 0 else [],
                    "raw_msg": raw_msg[:120]
                })

# B. From full_telegram_scrape_today.json
scrape_json = SCRATCH_DIR / "full_telegram_scrape_today.json"
if scrape_json.exists():
    try:
        scrape_data = json.load(open(scrape_json, encoding="utf-8"))
        ch_dict = scrape_data.get("channels", {})
        for ch_name, cdata in ch_dict.items():
            for sig_item in cdata.get("signals", []):
                t_str = sig_item.get("time", "")
                try:
                    dt = datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                if dt < from_time:
                    continue
                s = sig_item.get("signal", {})
                action = s.get("action", "").upper()
                symbols = s.get("symbols", [])
                sym = symbols[0] if symbols else "GOLD"
                if sym in ("XAUUSD", "GOLD"): sym = "GOLD"
                entry = s.get("entry") or 0.0
                sl = s.get("sl") or 0.0
                tps = s.get("tps") or []

                sig_id = f"{ch_name}_{sym}_{action}_{entry}_{dt.strftime('%Y%m%d%H%M')}"
                if sig_id not in seen_signatures:
                    seen_signatures.add(sig_id)
                    all_signals.append({
                        "timestamp": dt,
                        "channel": ch_name,
                        "symbol": sym,
                        "action": action,
                        "entry": entry,
                        "sl": sl,
                        "tps": tps,
                        "raw_msg": sig_item.get("text", "")[:120]
                    })
    except Exception as e:
        print(f"Error loading scrape json: {e}")

print(f"Total Unique Valid Signals from Last 3 Days: {len(all_signals)}")

# 3. Simulate Each Signal Under Both Modes
def simulate_both_modes(sig):
    sym = sig["symbol"]
    action = sig["action"]
    sig_time = sig["timestamp"]
    stated_entry = sig["entry"]
    stated_sl = sig["sl"]
    stated_tps = sig["tps"]

    df = get_m1_data(sym)
    if df is None or len(df) == 0:
        return None

    df_after = df.loc[df.index >= sig_time]
    if len(df_after) < 5:
        return None

    pip_size = get_pip_size(sym)
    market_open = df_after['open'].iloc[0]

    # Entry price
    if stated_entry and abs(stated_entry - market_open) <= (30 * pip_size):
        entry_price = stated_entry
    else:
        entry_price = market_open

    # SL price
    default_sl_dist = 40 * pip_size if sym == "GOLD" else 35 * pip_size
    if stated_sl and ((action == "BUY" and stated_sl < entry_price) or (action == "SELL" and stated_sl > entry_price)):
        original_sl = stated_sl
    else:
        original_sl = entry_price - default_sl_dist if action == "BUY" else entry_price + default_sl_dist

    # TPs
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

    # ── Simulation 1: Mode A (Premature TSL / Live Behavior) ──
    # Moves SL to Entry + 0.25 as soon as profit reaches 20 pips ($2.00 on Gold) or TP1
    be_threshold = 20.0 * pip_size  # $2.00 on Gold
    be_sl = entry_price + (0.25 if sym == "GOLD" else 2.0 * pip_size) if action == "BUY" else entry_price - (0.25 if sym == "GOLD" else 2.0 * pip_size)
    
    sl_mode_a = original_sl
    pnl_pips_a = 0.0
    outcome_a = "OPEN"
    hit_be_a = False
    exit_price_a = entry_price

    for idx, (bar_time, row) in enumerate(df_after.iterrows()):
        high = row['high']
        low = row['low']

        if action == "BUY":
            # Check if profit reached 20 pips ($2.00) -> move to Breakeven
            if not hit_be_a and (high - entry_price) >= be_threshold:
                hit_be_a = True
                sl_mode_a = be_sl

            # Check SL hit
            if low <= sl_mode_a:
                exit_price_a = sl_mode_a
                outcome_a = "BREAKEVEN" if hit_be_a else "LOSS_SL"
                break

            # Check TP1 hit
            if not hit_be_a and high >= tp1:
                hit_be_a = True
                sl_mode_a = be_sl

            # Check TP3 max hit
            if high >= tp3:
                exit_price_a = tp3
                outcome_a = "WIN_TP3"
                break
        else: # SELL
            if not hit_be_a and (entry_price - low) >= be_threshold:
                hit_be_a = True
                sl_mode_a = be_sl

            if high >= sl_mode_a:
                exit_price_a = sl_mode_a
                outcome_a = "BREAKEVEN" if hit_be_a else "LOSS_SL"
                break

            if not hit_be_a and low <= tp1:
                hit_be_a = True
                sl_mode_a = be_sl

            if low <= tp3:
                exit_price_a = tp3
                outcome_a = "WIN_TP3"
                break

    pnl_dist_a = (exit_price_a - entry_price) if action == "BUY" else (entry_price - exit_price_a)
    pnl_pips_a = pnl_dist_a / pip_size
    net_usd_a = calc_pnl_usd(sym, pnl_pips_a) - (0.53 if sym == "GOLD" else 0.25)

    # ── Simulation 2: Mode B (Extended Hold / Healthy Breathing Room) ──
    # Leaves original SL intact until TP1. After TP1, trails with 3.5 points ($35) breathing room or trails to TP1 after TP2
    sl_mode_b = original_sl
    pnl_pips_b = 0.0
    outcome_b = "OPEN"
    hit_tp1_b = False
    hit_tp2_b = False
    exit_price_b = entry_price

    for idx, (bar_time, row) in enumerate(df_after.iterrows()):
        high = row['high']
        low = row['low']

        if action == "BUY":
            # Check SL hit
            if low <= sl_mode_b:
                exit_price_b = sl_mode_b
                outcome_b = "LOSS_SL" if not hit_tp1_b else ("WIN_RUNNER_TSL" if sl_mode_b > entry_price else "BREAKEVEN")
                break

            # Check TP1 hit
            if not hit_tp1_b and high >= tp1:
                hit_tp1_b = True
                # Give 3.5 pts buffer below TP1 rather than slamming to entry!
                breathing_sl = tp1 - (3.50 if sym == "GOLD" else 30 * pip_size)
                if breathing_sl > sl_mode_b:
                    sl_mode_b = breathing_sl

            # Check TP2 hit
            if hit_tp1_b and not hit_tp2_b and high >= tp2:
                hit_tp2_b = True
                sl_mode_b = tp1  # Lock in TP1 profit completely

            # Check TP3 hit
            if high >= tp3:
                exit_price_b = tp3
                outcome_b = "WIN_TP3"
                break
        else: # SELL
            if high >= sl_mode_b:
                exit_price_b = sl_mode_b
                outcome_b = "LOSS_SL" if not hit_tp1_b else ("WIN_RUNNER_TSL" if sl_mode_b < entry_price else "BREAKEVEN")
                break

            if not hit_tp1_b and low <= tp1:
                hit_tp1_b = True
                breathing_sl = tp1 + (3.50 if sym == "GOLD" else 30 * pip_size)
                if breathing_sl < sl_mode_b:
                    sl_mode_b = breathing_sl

            if hit_tp1_b and not hit_tp2_b and low <= tp2:
                hit_tp2_b = True
                sl_mode_b = tp1

            if low <= tp3:
                exit_price_b = tp3
                outcome_b = "WIN_TP3"
                break

    pnl_dist_b = (exit_price_b - entry_price) if action == "BUY" else (entry_price - exit_price_b)
    pnl_pips_b = pnl_dist_b / pip_size
    net_usd_b = calc_pnl_usd(sym, pnl_pips_b) - (0.53 if sym == "GOLD" else 0.25)

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
        "mode_a_outcome": outcome_a,
        "mode_a_exit": round(exit_price_a, 2),
        "mode_a_pips": round(pnl_pips_a, 1),
        "mode_a_net_usd": round(net_usd_a, 2),
        "mode_b_outcome": outcome_b,
        "mode_b_exit": round(exit_price_b, 2),
        "mode_b_pips": round(pnl_pips_b, 1),
        "mode_b_net_usd": round(net_usd_b, 2),
        "wicked_prematurely": (outcome_a == "BREAKEVEN" and net_usd_b > 5.0)
    }

print("Running comparative simulations across all signals...")
sim_results = []
for sig in all_signals:
    res = simulate_both_modes(sig)
    if res:
        sim_results.append(res)

print(f"Simulations Completed: {len(sim_results)} valid trade setups tested")

# 4. Aggregations & Comparison
total_trades = len(sim_results)

# Mode A totals
wins_a = sum(1 for r in sim_results if r["mode_a_net_usd"] > 0)
be_a = sum(1 for r in sim_results if r["mode_a_outcome"] == "BREAKEVEN")
loss_a = sum(1 for r in sim_results if r["mode_a_net_usd"] <= 0 and r["mode_a_outcome"] != "BREAKEVEN")
net_a = sum(r["mode_a_net_usd"] for r in sim_results)

# Mode B totals
wins_b = sum(1 for r in sim_results if r["mode_b_net_usd"] > 0)
loss_b = sum(1 for r in sim_results if r["mode_b_net_usd"] <= 0)
net_b = sum(r["mode_b_net_usd"] for r in sim_results)

wicked_count = sum(1 for r in sim_results if r["wicked_prematurely"])
wicked_lost_profit = sum((r["mode_b_net_usd"] - r["mode_a_net_usd"]) for r in sim_results if r["wicked_prematurely"])

print("\n" + "=" * 80)
print("  COMPARATIVE RESULTS: PREMATURE TSL (MODE A) VS EXTENDED HOLD (MODE B)")
print("=" * 80)
print(f"Total Trades Evaluated: {total_trades}")
print(f"\nMODE A (Premature TSL / Live Moving to BE at +20 pips):")
print(f"  Wins: {wins_a} | Breakevens: {be_a} | Losses: {loss_a}")
print(f"  Win Rate: {wins_a/total_trades*100:.1f}%")
print(f"  Total Net USD: ${net_a:.2f}")

print(f"\nMODE B (Extended Hold / Healthy Breathing Room):")
print(f"  Wins: {wins_b} | Losses: {loss_b}")
print(f"  Win Rate: {wins_b/total_trades*100:.1f}%")
print(f"  Total Net USD: ${net_b:.2f}")

print(f"\n🚨 PREMATURE WICK CASUALTIES:")
print(f"  Trades wicked at Breakeven that subsequently hit TP2/TP3: {wicked_count} trades")
print(f"  Total Profit Lost due to Early TSL: +${wicked_lost_profit:.2f}")

# Channel by channel breakdown
ch_stats = defaultdict(lambda: {"trades": 0, "net_a": 0.0, "net_b": 0.0, "wicked": 0, "diff": 0.0})
for r in sim_results:
    ch = r["channel"]
    ch_stats[ch]["trades"] += 1
    ch_stats[ch]["net_a"] += r["mode_a_net_usd"]
    ch_stats[ch]["net_b"] += r["mode_b_net_usd"]
    if r["wicked_prematurely"]:
        ch_stats[ch]["wicked"] += 1
    ch_stats[ch]["diff"] += (r["mode_b_net_usd"] - r["mode_a_net_usd"])

# Match with actual 111 live MT5 deals from 48h_channel_performance.json
perf_file = SCRATCH_DIR / "48h_channel_performance.json"
live_matched_comparison = []
if perf_file.exists():
    try:
        live_data = json.load(open(perf_file, encoding="utf-8"))
        for ch_name, ch_info in live_data.get("channels", {}).items():
            for deal in ch_info.get("deals", []):
                pos_id = deal.get("pos_id")
                deal_sym = deal.get("symbol")
                deal_time_str = deal.get("entry_time", "").replace(" UTC", "")
                deal_net = deal.get("net_pnl", 0.0)
                exit_comm = deal.get("exit_comment", "")
                
                # Check if this deal was wicked out at breakeven / small profit
                is_micro_exit = (0.0 <= deal_net <= 2.0) and "[sl " in exit_comm
                
                # Find corresponding simulation in sim_results
                matched_sim = None
                for sr in sim_results:
                    if sr["symbol"] == deal_sym and sr["timestamp"][:14] in deal_time_str:
                        matched_sim = sr
                        break
                
                if matched_sim:
                    live_matched_comparison.append({
                        "pos_id": pos_id,
                        "channel": ch_name,
                        "symbol": deal_sym,
                        "entry_time": deal_time_str,
                        "live_net_pnl": deal_net,
                        "exit_comment": exit_comm,
                        "is_micro_exit": is_micro_exit,
                        "mode_a_pnl": matched_sim["mode_a_net_usd"],
                        "mode_b_pnl": matched_sim["mode_b_net_usd"],
                        "mode_b_outcome": matched_sim["mode_b_outcome"],
                        "hold_gain": round(matched_sim["mode_b_net_usd"] - deal_net, 2)
                    })
    except Exception as e:
        print(f"Error matching live deals: {e}")

# Save detailed output to JSON for deep analysis
output_summary = {
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "period": "Last 3 Days (2026-09-21 00:00 UTC to 2026-09-23 13:00 UTC)",
    "summary": {
        "total_trades": total_trades,
        "mode_a_premature_tsl": {
            "wins": wins_a,
            "breakevens": be_a,
            "losses": loss_a,
            "win_rate": round(wins_a/total_trades*100, 1),
            "net_usd": round(net_a, 2)
        },
        "mode_b_extended_hold": {
            "wins": wins_b,
            "losses": loss_b,
            "win_rate": round(wins_b/total_trades*100, 1),
            "net_usd": round(net_b, 2)
        },
        "premature_tsl_impact": {
            "wicked_trades_count": wicked_count,
            "profit_lost_usd": round(wicked_lost_profit, 2)
        }
    },
    "live_deals_matched": live_matched_comparison,
    "channel_comparison": {k: {sk: (round(sv, 2) if isinstance(sv, float) else sv) for sk, sv in v.items()} for k, v in ch_stats.items()},
    "sample_wicked_trades": [
        {k: (bool(v) if isinstance(v, (bool, np.bool_)) else v) for k, v in r.items()}
        for r in sim_results if r["wicked_prematurely"]
    ][:30]
}

out_path = SCRATCH_DIR / "3days_tsl_vs_hold_comparison.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output_summary, f, indent=2, default=str)

print(f"\nDetailed report saved to: {out_path}")
print(f"Live Deals Matched: {len(live_matched_comparison)}")
micro_exits = [d for d in live_matched_comparison if d["is_micro_exit"]]
print(f"Live Micro-Exits (Wicked out at +$0 to +$2): {len(micro_exits)}")
total_hold_gain = sum(d["hold_gain"] for d in live_matched_comparison if d["hold_gain"] > 0)
print(f"Potential Gain if Live Trades were Held with Breathing Room: +${total_hold_gain:.2f}")

mt5.shutdown()

