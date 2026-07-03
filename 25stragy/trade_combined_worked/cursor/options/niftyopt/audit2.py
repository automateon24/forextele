#!/usr/bin/env python3
"""Round 2 audit after fixes — find remaining leaks and next improvements."""
import sys; sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd, numpy as np
from collections import defaultdict
from BACKTEST_V6_PROFILED import run_v6, load_option_data, load_eod_data, label_days

opt = load_option_data()
eod = load_eod_data()
trades = run_v6(opt, eod)
df = pd.DataFrame([t.__dict__ for t in trades])
df['entry_hhmm'] = pd.to_datetime(df['entry_time']).apply(lambda x: x.hour*100+x.minute)

print("="*65)
print("A. TREND_FOLLOWING — 3 trades 33% WR, is it worth keeping?")
print("="*65)
tf = df[df['strategy']=='TREND_FOLLOWING']
for _, r in tf.iterrows():
    print(f"  {str(r['date'])[:10]}  {r['direction']}  {r['regime']:<15}  entry {r['entry_hhmm']}  {r['exit_reason']}  Rs{r['pnl_rs']:+,.0f}")
print(f"  Total TF: Rs{tf['pnl_rs'].sum():+,.0f}  — only 1 winner out of 3")

print("\n" + "="*65)
print("B. DAY_HIGH_BEARISH remaining TIME exits — what patterns?")
print("="*65)
dhb_time = df[(df['strategy']=='DAY_HIGH_BEARISH') & (df['exit_reason']=='TIME')]
for _, r in dhb_time.iterrows():
    print(f"  {str(r['date'])[:10]}  entry {r['entry_hhmm']}  {r['regime']:<15}  Rs{r['pnl_rs']:+,.0f}")
print(f"  DHB wins now: {(df[df['strategy']=='DAY_HIGH_BEARISH']['won']).sum()}/24  WR {(df[df['strategy']=='DAY_HIGH_BEARISH']['won']).mean()*100:.0f}%")

print("\n" + "="*65)
print("C. UNCOVERED DAYS — what type of market were they?")
print("="*65)
regimes = label_days(opt)
all_days = sorted(opt['date'].unique())
traded_days = set(df['date'].unique())
uncovered = [d for d in all_days if d not in traded_days and regimes.get(d) in {'TRENDING_BULL','TRENDING_BEAR','NORMAL'}]
print(f"  Total uncovered tradeable days: {len(uncovered)}")

# Check what kind of days they were by looking at gap, range, direction
eod_indexed = eod.set_index('dt') if 'dt' in eod.columns else eod
for d in uncovered[:20]:
    regime = regimes.get(d,'?')
    # Spot open/close from opt data
    day_opt = opt[opt['date']==d]
    if day_opt.empty: continue
    c15 = day_opt.groupby(pd.Grouper(key='ts_ist', freq='15min')).agg(
        open=('spot','first'), close=('spot','last'),
        high=('spot','max'), low=('spot','min')
    ).dropna()
    if len(c15) < 4: continue
    day_open  = float(c15.iloc[0]['open'])
    day_close = float(c15.iloc[-1]['close'])
    day_high  = float(c15['high'].max())
    day_low   = float(c15['low'].min())
    day_range = day_high - day_low
    direction = 'UP' if day_close > day_open else 'DOWN'
    print(f"  {str(d)[:10]}  {regime:<15}  {direction}  range={day_range:.0f}  open={day_open:.0f}  close={day_close:.0f}")

print("\n" + "="*65)
print("D. ENHANCED_BULLISH — firing at all? Profile is in active set")
print("="*65)
eb = df[df['strategy']=='ENHANCED_BULLISH']
print(f"  ENHANCED_BULLISH fired: {len(eb)} times")
if len(eb) > 0:
    for _, r in eb.iterrows():
        print(f"    {str(r['date'])[:10]}  {r['direction']}  Rs{r['pnl_rs']:+,.0f}  {r['exit_reason']}")

print("\n" + "="*65)
print("E. DAY_HIGH_BEARISH WR by regime — should we gate it?")
print("="*65)
dhb = df[df['strategy']=='DAY_HIGH_BEARISH']
for regime, g in dhb.groupby('regime'):
    wr = g['won'].mean()*100
    print(f"  {regime:<18}  {len(g):>3} trades  {wr:.0f}% WR  Rs{g['pnl_rs'].sum():+,.0f}  avg Rs{g['pnl_rs'].mean():+,.0f}")

print("\n" + "="*65)
print("F. Can we improve by tightening TSL_ACTIVATE threshold?")
print("="*65)
tsl_df = df[df['exit_reason']=='TSL']
print(f"  Current TSL exits: {len(tsl_df)}  avg Rs{tsl_df['pnl_rs'].mean():+,.0f}")
print(f"  Distribution: min={tsl_df['pnl_pts'].min():.0f}  25p={tsl_df['pnl_pts'].quantile(.25):.0f}  "
      f"median={tsl_df['pnl_pts'].quantile(.5):.0f}  75p={tsl_df['pnl_pts'].quantile(.75):.0f}  max={tsl_df['pnl_pts'].max():.0f}")
print(f"  TSL exits > 20pts profit (big movers): {(tsl_df['pnl_pts']>20).sum()}")
print(f"  TSL exits 8-20pts (modest): {((tsl_df['pnl_pts']>=8)&(tsl_df['pnl_pts']<=20)).sum()}")

print("\n" + "="*65)
print("G. Same-day strategy pair analysis — which pairs work best together?")
print("="*65)
daily_strats = df.groupby('date').apply(lambda g: sorted(g['strategy'].tolist()))
pair_counts = defaultdict(lambda: {'count':0,'total':0})
for date, strats in daily_strats.items():
    day_pnl = df[df['date']==date]['pnl_rs'].sum()
    if len(strats) == 2:
        key = tuple(strats)
        pair_counts[key]['count'] += 1
        pair_counts[key]['total'] += day_pnl
for pair, data in sorted(pair_counts.items(), key=lambda x: x[1]['total'], reverse=True)[:8]:
    print(f"  {pair[0][:20]} + {pair[1][:20]}  n={data['count']}  total Rs{data['total']:+,.0f}  avg Rs{data['total']/data['count']:+,.0f}")
