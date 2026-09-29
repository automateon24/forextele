import json
from pathlib import Path

p = Path(r"C:\anlyzeforex\forextele\scratch\3days_tsl_vs_hold_comparison.json")
data = json.load(open(p, encoding="utf-8"))

summary = data.get("summary", {})
print("=" * 85)
print("  3-DAY SYSTEM PERFORMANCE: PREMATURE TSL (MODE A) VS EXTENDED HOLD (MODE B)")
print("=" * 85)
print(f"Total Trade Setups Tested: {summary.get('total_trades')}")
ma = summary.get('mode_a_premature_tsl', {})
mb = summary.get('mode_b_extended_hold', {})
imp = summary.get('premature_tsl_impact', {})

print(f"\n1. MODE A (Premature TSL — Move to BE at +20 pips):")
print(f"   Wins: {ma.get('wins')} | Breakevens: {ma.get('breakevens')} | Losses: {ma.get('losses')}")
print(f"   Win Rate: {ma.get('win_rate')}%")
print(f"   Net USD: ${ma.get('net_usd')}")

print(f"\n2. MODE B (Extended Hold / Breathing Room):")
print(f"   Wins: {mb.get('wins')} | Losses: {mb.get('losses')}")
print(f"   Win Rate: {mb.get('win_rate')}%")
print(f"   Net USD: ${mb.get('net_usd')}")

print(f"\n3. PREMATURE WICK IMPACT:")
print(f"   Trades Wicked at BE that Hit TP2/TP3: {imp.get('wicked_trades_count')}")
print(f"   Profit Lost Due to Early TSL: +${imp.get('profit_lost_usd')}")

print("\n" + "=" * 85)
print(f"{'Channel':<35} | {'Trades':>6} | {'Mode A ($)':>10} | {'Mode B ($)':>10} | {'Wicked':>6} | {'Diff ($)':>10}")
print("-" * 85)
comp = data.get("channel_comparison", {})
for k, v in sorted(comp.items(), key=lambda x: x[1]["diff"], reverse=True)[:25]:
    ch_clean = k.encode('ascii', 'ignore').decode('ascii').strip()
    print(f"{ch_clean[:34]:<35} | {v['trades']:>6} | {v['net_a']:>10.2f} | {v['net_b']:>10.2f} | {v['wicked']:>6} | {v['diff']:>10.2f}")

print("\n" + "=" * 85)
print("  ACTUAL LIVE DEALS COMPARISON (TOP WICKED LIVE TRADES)")
print("=" * 85)
live_deals = data.get("live_deals_matched", [])
print(f"Total Live Deals Matched: {len(live_deals)}")
wicked_live = [d for d in live_deals if d.get("hold_gain", 0) > 10.0]
print(f"Live Deals That Suffered Heavily from Early TSL (> $10 missed): {len(wicked_live)}")
print(f"\n{'Ticket':<11} | {'Channel':<24} | {'Sym':<5} | {'Live PnL':>8} | {'Mode B PnL':>10} | {'Missed ($)':>10} | Mode B Outcome")
print("-" * 90)
for d in sorted(wicked_live, key=lambda x: x["hold_gain"], reverse=True)[:20]:
    ch_c = d["channel"].encode('ascii', 'ignore').decode('ascii').strip()
    print(f"{d['pos_id']:<11} | {ch_c[:23]:<24} | {d['symbol']:<5} | {d['live_net_pnl']:>8.2f} | {d['mode_b_pnl']:>10.2f} | {d['hold_gain']:>10.2f} | {d['mode_b_outcome']}")
