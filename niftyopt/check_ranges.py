import sys
sys.path.insert(0, 'c:/cursor/options/niftyopt')
from BACKTEST_V3_TUNED import load_option_data

opt = load_option_data()

daily = opt.groupby('date')['spot'].agg(['min', 'max'])
daily['range'] = daily['max'] - daily['min']
daily_open = opt.groupby('date')['spot'].first()
daily_close = opt.groupby('date')['spot'].last()
daily['open'] = daily_open
daily['close'] = daily_close
daily['move'] = (daily['close'] - daily['open']).abs()
daily['year'] = [str(d)[:4] for d in daily.index]

print("=== Daily Range (High-Low) stats ===")
print(daily['range'].describe().round(1))
print()
for pct in [50, 75, 90, 95, 99]:
    v = daily['range'].quantile(pct / 100)
    print(f"  {pct}th pct: {v:.0f} pts")

print()
print("=== Abs close-vs-open move stats ===")
print(daily['move'].describe().round(1))
for pct in [50, 75, 90, 95]:
    v = daily['move'].quantile(pct / 100)
    print(f"  {pct}th pct: {v:.0f} pts")

print()
print("=== By year ===")
for yr, grp in daily.groupby('year'):
    print(f"  {yr}  avg_range={grp['range'].mean():.0f}  avg_move={grp['move'].mean():.0f}  "
          f"  days>{150}pts_move: {(grp['move']>150).sum()}")
