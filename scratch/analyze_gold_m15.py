import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

mt5.initialize()
now = datetime.now(timezone.utc)
from_date = now - timedelta(days=35)
rates = mt5.copy_rates_range('GOLD', mt5.TIMEFRAME_M1, from_date, now)
mt5.shutdown()

df = pd.DataFrame(rates)
df['time_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
df.set_index('time_utc', inplace=True)
df.sort_index(inplace=True)

dates = np.unique(df.index.date)

print("=== M15 ASIAN OPEN TRADE INSPECTION (PAST 30 DAYS) ===")
mfe_list = []
mae_list = []
ranges = []

for d in dates:
    day_df = df[df.index.date == d]
    if len(day_df) < 60:
        continue
    asian_start = day_df.index[0]
    if asian_start.hour > 3:
        continue
    ref = day_df[(day_df.index >= asian_start) & (day_df.index < asian_start + timedelta(minutes=15))]
    if len(ref) < 15:
        continue
    ref_high = ref['high'].max()
    ref_low = ref['low'].min()
    ref_size = ref_high - ref_low
    ranges.append(ref_size)
    
    post = day_df[(day_df.index >= asian_start + timedelta(minutes=15)) & (day_df.index <= asian_start + timedelta(hours=6))]
    
    broken_bull = post['high'].max() > ref_high + 0.20
    broken_bear = post['low'].min() < ref_low - 0.20
    
    if broken_bull:
        break_bars = post[post['high'] > ref_high + 0.20]
        t_break = break_bars.index[0]
        retest_bars = post[(post.index > t_break) & (post['low'] <= ref_high + 0.25) & (post['high'] >= ref_high - 0.25)]
        if len(retest_bars) > 0:
            t_entry = retest_bars.index[0]
            entry_p = ref_high + 0.25
            future = post[post.index >= t_entry]
            mfe = future['high'].max() - entry_p
            mae = entry_p - future['low'].min()
            mfe_list.append(mfe)
            mae_list.append(mae)
            print(f"{d} | BULL | Range: ${ref_size:.2f} | Entry: {entry_p:.2f} | MFE: +${mfe:.2f} | MAE: -${mae:.2f}")
    elif broken_bear:
        break_bars = post[post['low'] < ref_low - 0.20]
        t_break = break_bars.index[0]
        retest_bars = post[(post.index > t_break) & (post['high'] >= ref_low - 0.25) & (post['low'] <= ref_low + 0.25)]
        if len(retest_bars) > 0:
            t_entry = retest_bars.index[0]
            entry_p = ref_low - 0.25
            future = post[post.index >= t_entry]
            mfe = entry_p - future['low'].min()
            mae = future['high'].max() - entry_p
            mfe_list.append(mfe)
            mae_list.append(mae)
            print(f"{d} | BEAR | Range: ${ref_size:.2f} | Entry: {entry_p:.2f} | MFE: +${mfe:.2f} | MAE: -${mae:.2f}")

print(f"\nAverage Opening 15m Range: ${np.mean(ranges):.2f}")
print(f"Average MFE (Max Favorable Profit Excursion): +${np.mean(mfe_list):.2f}")
print(f"Average MAE (Max Adverse Drawdown): -${np.mean(mae_list):.2f}")
