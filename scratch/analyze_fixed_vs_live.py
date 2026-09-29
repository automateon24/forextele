import json
from pathlib import Path

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
SCRATCH_DIR = BASE_DIR / "scratch"

fixed_res = json.load(open(SCRATCH_DIR / "pure_fixed_sl_no_tsl_results.json", encoding="utf-8"))
live_res = json.load(open(SCRATCH_DIR / "48h_channel_performance.json", encoding="utf-8"))

deals = [d for ch in live_res.get("channels", {}).values() for d in ch.get("deals", [])]
print(f"Total Live Closed Positions: {len(deals)}")
print(f"Total Live Realized Net PnL: ${sum(d.get('net_pnl', 0) for d in deals):.2f}")

ms = fixed_res.get("modes_summary", {})
print("\n" + "=" * 80)
print("  COMPREHENSIVE BACKTEST SUMMARY (901 TRADES OVER LAST 3 DAYS)")
print("=" * 80)
for mode_name, stats in ms.items():
    print(f"Mode: {mode_name:<20} | Wins: {stats.get('wins', 0):>4} | WR: {stats.get('win_rate', 0):>5.1f}% | Net USD: ${stats.get('net_usd', 0):>9.2f} | Gain vs Old TSL: ${stats.get('gain_vs_tsl', 0):>8.2f}")

print("\n" + "=" * 80)
print("  TOP WINNING CHANNELS UNDER PURE FIXED SL & TARGETS (NO TSL AT ALL)")
print("=" * 80)
print(f"{'Channel':<35} | {'Trades':>6} | {'Premature TSL':>13} | {'Fixed TP1':>10} | {'Fixed TP2':>10} | {'Hybrid 50/50':>12}")
print("-" * 95)
ch_data = fixed_res.get("channels", {})
for ch, v in sorted(ch_data.items(), key=lambda x: x[1].get("net_tp2", 0), reverse=True)[:15]:
    ch_c = ch.encode('ascii', 'ignore').decode('ascii').strip()
    print(f"{ch_c[:34]:<35} | {v.get('trades', 0):>6} | ${v.get('net_tsl', 0):>12.2f} | ${v.get('net_tp1', 0):>9.2f} | ${v.get('net_tp2', 0):>9.2f} | ${v.get('net_hyb', 0):>11.2f}")
