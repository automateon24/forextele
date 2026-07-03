import sys, pandas as pd, glob, os
sys.path.insert(0,'c:/cursor/options/niftyopt')
from BACKTEST_V3_TUNED import build_15min_spot
UTC_OFFSET = pd.Timedelta(hours=5, minutes=30)

pqs = sorted(glob.glob('data/raw/BANKNIFTY_expired_2025-02-03_2025-03-05_*_CALL_1min_MONTH_1.parquet'))
frames = []
for p in pqs:
    df = pd.read_parquet(p)
    df['option_type_flag'] = 'CE'
    ts = pd.to_datetime(df['timestamp'])
    if ts.dt.tz is not None:
        ts = ts.dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
    elif ts.dt.hour.median() <= 7:
        ts = ts + UTC_OFFSET
    df['timestamp'] = ts
    df['ts_ist'] = ts
    df['date'] = ts.dt.date
    df['hhmm'] = ts.dt.hour*100 + ts.dt.minute
    frames.append(df)

data = pd.concat(frames, ignore_index=True)
day = sorted(data.date.unique())[10]
day_data = data[data['date']==day].copy()
c15 = build_15min_spot(day_data)
print('c15 columns:', list(c15.columns))
print('c15 dtypes:', c15.dtypes.to_dict())
print()
print('c15 head:')
print(c15.head(6).to_string())
print()

# Simulate exactly what run_index does
def _get_ts(bar):
    v = bar.get('ts_ist') if hasattr(bar,'get') else getattr(bar,'ts_ist',None)
    return pd.Timestamp(v) if v is not None else pd.Timestamp('2000-01-01')

print('=== hhmm trace ===')
for i in range(3, min(10, len(c15))):
    row = c15.iloc[i]
    ts = _get_ts(row)
    hhmm = ts.hour*100 + ts.minute
    ts_val = row['ts_ist']
    print(f'bar {i}: ts_ist={ts_val}  _get_ts={ts}  hhmm={hhmm}')

# Also check: what hhmm is in day_data vs what c15 provides
print()
print('day_data hhmm range:', day_data['hhmm'].min(), '-', day_data['hhmm'].max())

# Now simulate opt_b lookup at a real armed time (e.g. hhmm=1000)
test_hhmm = 1000
opt_b = day_data[
    (day_data['option_type_flag'] == 'CE') &
    (day_data['strike'] == 'ATM') &
    (day_data['hhmm'] == test_hhmm)
]
print(f'\nopt_b at hhmm={test_hhmm}, ATM CE: {len(opt_b)} rows')
if len(opt_b) > 0:
    print(opt_b[['hhmm','strike','option_type_flag','close','spot']].head(3).to_string())
