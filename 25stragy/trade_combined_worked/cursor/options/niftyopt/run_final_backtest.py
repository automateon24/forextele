import sys
from datetime import date
sys.path.insert(0, 'c:/cursor/options/niftyopt')
from BACKTEST_V3_TUNED import run_backtest, load_option_data, load_eod_data
from collections import defaultdict

opt_data = load_option_data()
eod_data = load_eod_data()
trades = run_backtest(opt_data, eod_data)

CAPITAL_PER_STRAT = 50000
TOTAL_CAPITAL = 1000000  # 10 lakhs

# Dynamic days from actual data
all_dates = sorted(set(t.date for t in trades)) if trades else []
DAYS = opt_data['date'].nunique()
date_min = opt_data['date'].min()
date_max = opt_data['date'].max()

total = sum(t.pnl_rs for t in trades)

by_strat = defaultdict(list)
for t in trades:
    by_strat[t.strategy].append(t)

# Split by year for comparison
trades_2025 = [t for t in trades if str(t.date).startswith('2025')]
trades_2026 = [t for t in trades if str(t.date).startswith('2026')]
days_2025 = len(set(t.date for t in trades_2025)) or 1
days_2026 = len(set(t.date for t in trades_2026)) or 1

print("=" * 82)
print(f"FULL {DAYS}-DAY BACKTEST RESULTS  ({date_min} to {date_max})")
print("=" * 82)
print(f"Total PnL  : Rs {total:+,.0f}")
print(f"Daily avg  : Rs {total/DAYS:+,.0f}")
print(f"Monthly    : Rs {total/DAYS*22:+,.0f}  ({total/DAYS*22/TOTAL_CAPITAL*100:.1f}% on 10L)")
print(f"2025 PnL   : Rs {sum(t.pnl_rs for t in trades_2025):+,.0f}  ({days_2025} days, {len(trades_2025)} trades)")
print(f"2026 PnL   : Rs {sum(t.pnl_rs for t in trades_2026):+,.0f}  ({days_2026} days, {len(trades_2026)} trades)")
print()

print(f"{'Strategy':<30} {'N':>5} {'Win%':>5} {'Total PnL':>10} {'Avg/Day':>9} {'Day%':>6}  {'5%?'}")
print("-" * 82)

for s, ts in sorted(by_strat.items(), key=lambda x: sum(t.pnl_rs for t in x[1]), reverse=True):
    pnl = sum(t.pnl_rs for t in ts)
    wins = sum(1 for t in ts if t.won)
    wr = 100 * wins // max(len(ts), 1)
    avg_day = pnl / DAYS
    pct_day = avg_day / CAPITAL_PER_STRAT * 100
    if pct_day >= 5.0:
        tag = "YES 5%+"
    elif pct_day >= 3.0:
        tag = "~3-4%"
    elif pct_day >= 1.0:
        tag = "~1-2%"
    else:
        tag = "LOSS" if pnl < 0 else "<1%"
    print(f"{s:<30} {len(ts):>5} {wr:>4}% {pnl:>+10,.0f} {avg_day:>+9,.0f} {pct_day:>5.1f}%  {tag}")

print("-" * 82)
print(f"{'ALL COMBINED':<30} {len(trades):>5}      {total:>+10,.0f} {total/DAYS:>+9,.0f} {total/DAYS/TOTAL_CAPITAL*100:>5.2f}%  {'YES' if total/DAYS/TOTAL_CAPITAL*100>=5 else 'TARGET: 5%'}")
print()

# Per-year breakdown for top strategies
print("=" * 82)
print("PER-YEAR BREAKDOWN (2025 vs 2026)")
print("=" * 82)
print(f"{'Strategy':<30} {'2025 PnL':>10} {'2025 WR':>8} {'2026 PnL':>10} {'2026 WR':>8} {'Better?':>8}")
print("-" * 82)
for s in sorted(by_strat.keys()):
    t25 = [t for t in by_strat[s] if str(t.date).startswith('2025')]
    t26 = [t for t in by_strat[s] if str(t.date).startswith('2026')]
    p25 = sum(t.pnl_rs for t in t25)
    p26 = sum(t.pnl_rs for t in t26)
    w25 = f"{100*sum(1 for t in t25 if t.won)//max(len(t25),1)}%" if t25 else "n/a"
    w26 = f"{100*sum(1 for t in t26 if t.won)//max(len(t26),1)}%" if t26 else "n/a"
    better = "2026↑" if p26 > p25 else ("2025↑" if p25 > p26 else "same")
    if t25 or t26:
        print(f"{s:<30} {p25:>+10,.0f} {w25:>8} {p26:>+10,.0f} {w26:>8} {better:>8}")
print()

# UDHL detail
udhl = by_strat.get('ULTIMATE_DAY_HIGH_LOW', [])
if udhl:
    print("=" * 60)
    print("ULTIMATE_DAY_HIGH_LOW — Detailed")
    print("=" * 60)
    for yr in ['2025', '2026']:
        sub_yr = [t for t in udhl if str(t.date).startswith(yr)]
        if sub_yr:
            print(f"  {yr}: {len(sub_yr)} trades, PnL={sum(t.pnl_rs for t in sub_yr):+,.0f}")
            for d in ['CE','PE']:
                sub = [t for t in sub_yr if t.direction == d]
                if sub:
                    p = sum(t.pnl_rs for t in sub)
                    w = sum(1 for t in sub if t.won)
                    exits = defaultdict(int)
                    for t in sub: exits[t.exit_reason] += 1
                    print(f"    {d}: {len(sub)} trades, {w}/{len(sub)} wins ({100*w//len(sub)}%), PnL={p:+,.0f}, exits={dict(exits)}")
    print()
    print("  Sample 2026 trades (Apr-May):")
    udhl_2026 = sorted([t for t in udhl if str(t.date) >= '2026-04-01'], key=lambda x: x.date)
    for t in udhl_2026[:10]:
        print(f"  {str(t.date)[:10]} {t.direction} entry={t.entry_price:.0f} exit={t.exit_price:.0f} [{t.exit_reason}] PnL={t.pnl_rs:+,.0f}")
