"""Check actual premium ranges for ATM+4 (ZERO_HERO) and Fibonacci strikes (MAGIC_SQUARE)"""
import sys, warnings
warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
sys.path.insert(0, '.')
from BACKTEST_V3_TUNED import load_option_data, load_eod_data

opt_data = load_option_data()
eod_data = load_eod_data()
all_days = sorted(opt_data['date'].unique())

atm4_premiums = []
atm2_premiums = []
atm1_premiums = []
atm_premiums  = []

for day in all_days:
    day_data = opt_data[opt_data['date'] == day]
    for strike_label, lst in [('ATM+4', atm4_premiums), ('ATM+2', atm2_premiums),
                               ('ATM+1', atm1_premiums), ('ATM', atm_premiums)]:
        s = day_data[day_data['strike'] == strike_label]
        if len(s) == 0:
            continue
        # Get morning premiums (9:30-11:00) and afternoon (12:00-15:00)
        s = s.copy()
        s['hhmm'] = s['ts_ist'].dt.hour * 100 + s['ts_ist'].dt.minute
        morning = s[s['hhmm'].between(930, 1100)]
        if len(morning) > 0:
            lst.append(morning['close'].median())

print("=" * 70)
print("PREMIUM ANALYSIS BY STRIKE (morning 9:30-11:00 median)")
print("=" * 70)
for label, lst in [('ATM', atm_premiums), ('ATM+1', atm1_premiums),
                    ('ATM+2', atm2_premiums), ('ATM+4', atm4_premiums)]:
    if lst:
        arr = np.array(lst)
        print(f"\n{label} ({len(arr)} days):")
        print(f"  Min={arr.min():.0f}  p10={np.percentile(arr,10):.0f}  "
              f"p25={np.percentile(arr,25):.0f}  Median={np.median(arr):.0f}  "
              f"p75={np.percentile(arr,75):.0f}  p90={np.percentile(arr,90):.0f}  Max={arr.max():.0f}")
        in_9_60 = np.sum((arr >= 9) & (arr <= 60))
        in_50_400 = np.sum((arr >= 50) & (arr <= 400))
        print(f"  Days in 9-60 range: {in_9_60}/{len(arr)} = {100*in_9_60/len(arr):.0f}%")
        print(f"  Days in 50-400 range: {in_50_400}/{len(arr)} = {100*in_50_400/len(arr):.0f}%")
    else:
        print(f"\n{label}: NO DATA FOUND")

# Check what strikes exist at all
print("\n\nALL STRIKE LABELS IN DATA:")
print(opt_data['strike'].value_counts())
