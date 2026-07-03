#!/usr/bin/env python3
"""Diagnose thin months and find NORMAL regime uncovered days."""
import sys; sys.path.insert(0,'c:/cursor/options/niftyopt')
import pandas as pd, numpy as np
from BACKTEST_V6_PROFILED import run_v6, load_option_data, load_eod_data
from regime_detector import label_days

opt=load_option_data(); eod=load_eod_data()
trades=run_v6(opt,eod)
df=pd.DataFrame([t.__dict__ for t in trades])
df['month']=pd.to_datetime(df['date']).dt.to_period('M')
df['entry_hhmm']=pd.to_datetime(df['entry_time']).apply(lambda x: x.hour*100+x.minute)

print("="*65)
print("MONTHLY PnL breakdown (corrected):")
print("="*65)
monthly = df.groupby('month').agg(pnl=('pnl_rs','sum'),trades=('pnl_rs','count'),wr=('won','mean'))
for _,r in monthly.reset_index().iterrows():
    flag = ' << BELOW 5k' if r['pnl'] < 5000 else ''
    print(f"  {r['month']}  Rs{r['pnl']:+6,.0f}  {r['trades']:2} trades  {r['wr']*100:.0f}% WR{flag}")

print("\n" + "="*65)
print("MAR 2026 — only 2 trades why?")
print("="*65)
mar26 = df[df['month']=='2026-03']
print(f"  Trades this month: {len(mar26)}")
for _,r in mar26.iterrows():
    print(f"  {str(r['date'])[:10]}  {r['strategy']}  {r['exit_reason']}  Rs{r['pnl_rs']:+,.0f}")

regimes = label_days(opt)
mar_days = [d for d in sorted(opt['date'].unique()) if str(d)[:7]=='2026-03']
traded = set(df['date'].unique())
print(f"\n  All March 2026 trading days ({len(mar_days)}):")
for d in mar_days:
    status = 'TRADED' if d in traded else f'MISSED({regimes.get(d,"?")})'
    print(f"    {str(d)[:10]}  {status}")

print("\n" + "="*65)
print("FEB 2026 — only 9 trades Rs+1008 (78% WR but low total)")
print("="*65)
feb26 = df[df['month']=='2026-02']
for _,r in feb26.iterrows():
    print(f"  {str(r['date'])[:10]}  {r['strategy'][:18]}  {r['direction']}  "
          f"{r['exit_reason']}  Rs{r['pnl_rs']:+,.0f}")

print("\n" + "="*65)
print("NORMAL REGIME uncovered days — 18 remaining")
print("="*65)
norm_uncov = [d for d in sorted(opt['date'].unique())
              if d not in traded and regimes.get(d)=='NORMAL']
print(f"  Count: {len(norm_uncov)}")
for d in norm_uncov:
    day_opt = opt[opt['date']==d]
    c15 = day_opt.groupby(pd.Grouper(key='ts_ist',freq='15min')).agg(
        open=('spot','first'),close=('spot','last'),
        high=('spot','max'),low=('spot','min')).dropna()
    if len(c15)<3: continue
    o=float(c15.iloc[0]['open']); cl=float(c15.iloc[-1]['close'])
    rng=float(c15['high'].max())-float(c15['low'].min())
    direction='UP' if cl>o else 'DOWN'
    print(f"  {str(d)[:10]}  {direction}  range={rng:.0f}")

print("\n" + "="*65)
print("NORMAL regime uncovered — UP days analysis")
print("="*65)
norm_up=[d for d in norm_uncov if True]  # analyze all
moves=[]
for d in norm_uncov:
    day_opt=opt[opt['date']==d]
    c15=day_opt.groupby(pd.Grouper(key='ts_ist',freq='15min')).agg(
        open=('spot','first'),close=('spot','last'),
        high=('spot','max'),low=('spot','min')).dropna()
    if len(c15)<5: continue
    o=float(c15.iloc[0]['open']); cl=float(c15.iloc[-1]['close'])
    rng=float(c15['high'].max())-float(c15['low'].min())
    # Check what time the daily high/low was made
    highs=c15['high'].values; lows=c15['low'].values
    day_high_bar=int(np.argmax(highs))
    day_low_bar=int(np.argmin(lows))
    moves.append({'date':d,'direction':'UP' if cl>o else 'DOWN',
                  'range':rng,'high_bar':day_high_bar,'low_bar':day_low_bar})
mdf=pd.DataFrame(moves)
print(f"  UP days: {(mdf['direction']=='UP').sum()}  DOWN: {(mdf['direction']=='DOWN').sum()}")
print(f"  Avg range: {mdf['range'].mean():.0f}  Min: {mdf['range'].min():.0f}")
print(f"  Low range (<120pts): {(mdf['range']<120).sum()} days — may not be tradeable")
print(f"  Good range (>150pts): {(mdf['range']>150).sum()} days")
