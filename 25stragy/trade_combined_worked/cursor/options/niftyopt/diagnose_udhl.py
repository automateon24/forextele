import sys
sys.path.insert(0, 'c:/cursor/options/niftyopt')
from BACKTEST_V3_TUNED import run_backtest, load_option_data, load_eod_data
from collections import defaultdict

opt_data = load_option_data()
eod_data = load_eod_data()
trades = run_backtest(opt_data, eod_data)

by_strat = defaultdict(list)
for t in trades:
    by_strat[t.strategy].append(t)

CAPITAL = 50000

print("=" * 70)
print("PER-STRATEGY SUMMARY — 58 days (Feb-May 2025)")
print("= What daily % return each strategy generates on Rs 50k capital =")
print("=" * 70)
print(f"{'Strategy':<28} {'Trades':>6} {'Win%':>5} {'PnL':>9} {'Avg/trade':>10} {'Trades/wk':>10}")
print("-" * 70)

for s, ts in sorted(by_strat.items(), key=lambda x: sum(t.pnl_rs for t in x[1]), reverse=True):
    pnl = sum(t.pnl_rs for t in ts)
    wins = sum(1 for t in ts if t.won)
    wr = 100 * wins // max(len(ts), 1)
    avg_trade = pnl / len(ts)
    per_week = len(ts) / (58/5)   # trades per week
    print(f"{s:<28} {len(ts):>6} {wr:>4}% {pnl:>+9,.0f} {avg_trade:>+10,.0f} {per_week:>9.1f}x/wk")

print()
print("=" * 70)
print("HONEST ASSESSMENT: Can these strategies make 5%/day on Rs 50k capital?")
print("= 5%/day = Rs 2,500/day per strategy =")
print("=" * 70)
total = sum(t.pnl_rs for t in trades)
days = 58

# Group into tiers
print("\nTier 1 — Consistent positive (profitable every month):")
for s, ts in sorted(by_strat.items(), key=lambda x: sum(t.pnl_rs for t in x[1]), reverse=True):
    pnl = sum(t.pnl_rs for t in ts)
    if pnl > 3000 and len(ts) >= 5:
        avg_day = pnl / days
        pct = avg_day / CAPITAL * 100
        avg_win = sum(t.pnl_rs for t in ts if t.won) / max(sum(1 for t in ts if t.won), 1)
        print(f"  {s}: Rs {pnl:+,.0f} total | Rs {avg_day:+,.0f}/day avg | {pct:.2f}%/day | avg_win=Rs {avg_win:,.0f}")

print("\nTier 2 — Occasional big winners (low frequency but high RR):")
for s, ts in sorted(by_strat.items(), key=lambda x: sum(t.pnl_rs for t in x[1]), reverse=True):
    pnl = sum(t.pnl_rs for t in ts)
    if 0 < pnl <= 3000 or (pnl > 0 and len(ts) < 5):
        avg_win = sum(t.pnl_rs for t in ts if t.won) / max(sum(1 for t in ts if t.won), 1)
        print(f"  {s}: Rs {pnl:+,.0f} total | {len(ts)} trades | avg_win=Rs {avg_win:,.0f}")

print("\nTier 3 — Losers (need fix or disable):")
for s, ts in sorted(by_strat.items(), key=lambda x: sum(t.pnl_rs for t in x[1])):
    pnl = sum(t.pnl_rs for t in ts)
    if pnl < 0:
        avg_loss = sum(t.pnl_rs for t in ts if not t.won) / max(sum(1 for t in ts if not t.won), 1)
        print(f"  {s}: Rs {pnl:+,.0f} total | {len(ts)} trades | avg_loss=Rs {avg_loss:,.0f}")

print()
print("=" * 70)
print(f"COMBINED: Rs {total:+,.0f} over 58 days = Rs {total/days:+,.0f}/day = {total/days/1000000*100:.2f}% on 10L")
print()
print("REALITY CHECK vs YOUR MANUAL TRADING:")
print("  Your manual (13 trades, Apr-May 2026): Rs 69,420 = Rs 6,647/trade avg")
print("  That's ~1 trade/day with 69% win rate and 2.77 RR")
print("  Key: You target FULL day range (150-350 pts), not fixed % on premium")
print()
print("  Our backtest TSL exits are at 5%+10pts profit — too early for day-range targets")
print("  Fix needed: UDHL should use 'day range target' not fixed % target")
