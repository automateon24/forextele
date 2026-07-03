import pandas as pd, glob, os, numpy as np
raw = 'data/raw'

for idx in ['BANKNIFTY', 'SENSEX']:
    pqs = sorted(glob.glob(os.path.join(raw, f'{idx}_expired_*.parquet')))
    print(f'\n=== {idx}: {len(pqs)} files ===')
    for p in pqs[:6]:
        print(' ', os.path.basename(p))
    if len(pqs) > 6:
        print(f'  ... and {len(pqs)-6} more')
    if not pqs:
        continue

    df = pd.concat([pd.read_parquet(p) for p in pqs])
    df['ts']   = pd.to_datetime(df['timestamp'])
    df['date'] = df['ts'].dt.date
    df['hhmm'] = df['ts'].dt.hour * 100 + df['ts'].dt.minute

    print(f'  Columns: {list(df.columns)}')
    print(f'  Total rows: {len(df)}')
    print(f'  Unique dates: {df.date.nunique()}  ({df.date.min()} to {df.date.max()})')

    # option_type_flag
    if 'option_type_flag' in df.columns:
        vc = df['option_type_flag'].value_counts()
        print(f'  option_type_flag:\n{vc}')
    else:
        print('  option_type_flag: MISSING')

    # strike
    if 'strike' in df.columns:
        strikes = sorted(df['strike'].unique())
        print(f'  strikes ({len(strikes)} unique): {strikes[:10]}')
    else:
        print('  strike: MISSING')

    # spot
    if 'spot' in df.columns:
        sp = df['spot'].dropna()
        print(f'  spot: min={sp.min():.0f}  median={sp.median():.0f}  max={sp.max():.0f}  nulls={df.spot.isna().sum()}')
    else:
        print('  spot: MISSING')

    # close premium
    cl = df['close']
    cl = cl[cl > 0]
    print(f'  close (>0): p5={cl.quantile(0.05):.0f}  median={cl.median():.0f}  p95={cl.quantile(0.95):.0f}')

    # show a sample day
    sample_day = df['date'].unique()[5]
    day_df = df[(df['date'] == sample_day) & (df['hhmm'].between(930, 1000))]
    print(f'\n  Sample day {sample_day} 9:30-10:00 (first 5 rows):')
    cols = [c for c in ['ts','hhmm','strike','option_type_flag','open','high','low','close','spot','oi'] if c in day_df.columns]
    print(day_df[cols].head(5).to_string())

    # check what strat.strike maps to — in V7 build_15min_spot uses 'ATM' strike
    # let's see what 'strike' column vs 'spot' look like
    print(f'\n  strike vs spot comparison (sample 5 rows):')
    sample = df[(df['hhmm'] == 930)].head(5)
    if 'strike' in sample.columns and 'spot' in sample.columns:
        print(sample[['date','strike','spot','option_type_flag','close']].to_string())

print('\n\n=== CHECKING HOW run_index RESOLVES strat.strike ===')
# Look at what strat.strike values are set to in make_strategies()
import sys
sys.path.insert(0, 'c:/cursor/options/niftyopt')
from BACKTEST_V3_TUNED import make_strategies, PERIODS, STRIKES
strats = make_strategies()
for s in strats[:5]:
    print(f'  {s.name}: strike={s.strike}  direction={s.direction}')
