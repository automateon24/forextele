import sys
sys.path.insert(0, 'c:/cursor/options/niftyopt')
from BACKTEST_V3_TUNED import load_option_data
import pandas as pd

opt = load_option_data()
print("Columns:", opt.columns.tolist())
print()

# Check a single day
sample = opt[opt['date'] == opt['date'].iloc[0]]
print("Sample day:", opt['date'].iloc[0])
print("Spot range:", sample['spot'].min(), "to", sample['spot'].max())
spot = sample['spot']
day_open  = spot.iloc[0]
day_high  = spot.max()
day_low   = spot.min()
day_close = spot.iloc[-1]
daily_range = day_high - day_low
spot_vs_open = day_close - day_open
spot_vs_open_max = (spot - day_open).abs().max()
print(f"daily_range={daily_range:.1f}, spot_vs_open={spot_vs_open:.1f}, spot_vs_open_max={spot_vs_open_max:.1f}")

if 'iv' in sample.columns:
    print(f"IV present: min={sample['iv'].min():.4f} max={sample['iv'].max():.4f} mean={sample['iv'].mean():.4f}")
else:
    print("No IV column")

# Now manually apply the classify_from_stats logic
TREND_STRONG_MOVE_PTS = 150
HIGH_VOL_RANGE_PTS    = 400
RANGE_MAX_TREND_PTS   = 50
RANGE_MAX_RANGE_PTS   = 180
HIGH_IV_THRESHOLD     = 0.25

avg_iv = sample['iv'].mean() if 'iv' in sample.columns else 0.0

print()
print("=== Classification Debug ===")
print(f"daily_range >= {HIGH_VOL_RANGE_PTS}? {daily_range} -> {daily_range >= HIGH_VOL_RANGE_PTS}")
print(f"avg_iv >= {HIGH_IV_THRESHOLD}? {avg_iv:.4f} -> {avg_iv >= HIGH_IV_THRESHOLD}")
print(f"spot_vs_open_max >= {TREND_STRONG_MOVE_PTS}? {spot_vs_open_max:.1f} -> {spot_vs_open_max >= TREND_STRONG_MOVE_PTS}")

# Check what 'spot' column actually is
print()
print("Sample spot values (first 5):", sample['spot'].head().tolist())
print("Sample 'close' values (first 5):", sample['close'].head().tolist() if 'close' in sample.columns else "N/A")

# Check all days ranges
daily = opt.groupby('date')['spot'].agg(['min', 'max'])
daily['range'] = daily['max'] - daily['min']
print()
print(f"Days with range > {HIGH_VOL_RANGE_PTS}: {(daily['range'] > HIGH_VOL_RANGE_PTS).sum()} / {len(daily)}")
print(f"Days with range <= {HIGH_VOL_RANGE_PTS}: {(daily['range'] <= HIGH_VOL_RANGE_PTS).sum()} / {len(daily)}")
