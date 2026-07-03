#!/usr/bin/env python3
"""
Final deep audit — find every remaining improvement opportunity:
1. Months below 5% — what happened?
2. TREND_FOLLOWING 33% WR — keep or kill?
3. Remaining TIME exits — can any be converted or avoided?
4. 86 still-uncovered days — any catchable with simple conditions?
5. Confidence score vs WR correlation — can we filter low-conf?
"""
import sys; sys.path.insert(0,'c:/cursor/options/niftyopt')
import pandas as pd, numpy as np
from collections import defaultdict
from BACKTEST_V6_PROFILED import run_v6, load_option_data, load_eod_data
from regime_detector import label_days

opt=load_option_data(); eod=load_eod_data()
trades=run_v6(opt,eod)
df=pd.DataFrame([t.__dict__ for t in trades])
df['entry_hhmm']=pd.to_datetime(df['entry_time']).apply(lambda x: x.hour*100+x.minute)
df['month']=pd.to_datetime(df['date']).dt.to_period('M')

print("="*65)
print("1. MONTHLY PnL — which months below 5% target (Rs5000)?")
print("="*65)
monthly = df.groupby('month').agg(pnl=('pnl_rs','sum'), trades=('pnl_rs','count'),
                                   wr=('won','mean')).reset_index()
for _,r in monthly.iterrows():
    flag = ' <-- BELOW TARGET' if r['pnl'] < 5000 else ''
    print(f"  {r['month']}  Rs{r['pnl']:+6,.0f}  {r['trades']} trades  {r['wr']*100:.0f}% WR{flag}")

print("\n" + "="*65)
print("2. TREND_FOLLOWING — 3 trades 33% WR — kill it?")
print("="*65)
tf = df[df['strategy']=='TREND_FOLLOWING']
print(f"  Net: Rs{tf['pnl_rs'].sum():+,.0f}  over {len(tf)} trades")
print(f"  If removed: Rs{df[df['strategy']!='TREND_FOLLOWING']['pnl_rs'].sum():+,.0f} total")

print("\n" + "="*65)
print("3. REMAINING 26 TIME EXITS — breakdown")
print("="*65)
time_df = df[df['exit_reason']=='TIME'].copy()
pos = time_df[time_df['pnl_rs']>0]
neg = time_df[time_df['pnl_rs']<=0]
print(f"  Profitable TIME exits: {len(pos)}  total Rs{pos['pnl_rs'].sum():+,.0f}")
print(f"  Loss TIME exits:       {len(neg)}  total Rs{neg['pnl_rs'].sum():+,.0f}")
print(f"\n  Loss TIME exit detail:")
for _,r in neg.sort_values('pnl_rs').iterrows():
    print(f"    {str(r['date'])[:10]}  {r['strategy'][:20]}  {r['direction']}  "
          f"entry {r['entry_hhmm']}  Rs{r['pnl_rs']:+,.0f}")

print("\n" + "="*65)
print("4. CONFIDENCE SCORE vs WIN RATE — does conf predict wins?")
print("="*65)
bins=[0.60,0.70,0.75,0.80,0.85,0.88,0.92,1.0]
labels=['0.60-0.70','0.70-0.75','0.75-0.80','0.80-0.85','0.85-0.88','0.88-0.92','0.92+']
df['conf_bucket']=pd.cut(df['confidence'],bins=bins,labels=labels)
print("  Conf range    Trades  WR%   Avg PnL")
for b,g in df.groupby('conf_bucket',observed=True):
    if len(g)>0:
        print(f"  {b}   {len(g):>5}  {g['won'].mean()*100:>4.0f}%  Rs{g['pnl_rs'].mean():+,.0f}")

print("\n" + "="*65)
print("5. WHAT IS THE MIN CONFIDENCE THRESHOLD THAT MAXIMISES PnL?")
print("="*65)
for thresh in [0.70,0.75,0.78,0.80,0.82,0.84,0.86]:
    sub = df[df['confidence']>=thresh]
    if len(sub)>0:
        print(f"  conf>={thresh:.2f}: {len(sub):>3} trades  {sub['won'].mean()*100:.0f}% WR  "
              f"Rs{sub['pnl_rs'].sum():+,.0f}  avg Rs{sub['pnl_rs'].mean():+,.0f}")

print("\n" + "="*65)
print("6. UNCOVERED DAYS — still 86 uncovered total")
print("="*65)
regimes = label_days(opt)
all_days = sorted(opt['date'].unique())
traded = set(df['date'].unique())
uncovered = [d for d in all_days if d not in traded
             and regimes.get(d) in {'TRENDING_BULL','TRENDING_BEAR','NORMAL'}]
print(f"  Tradeable but uncovered: {len(uncovered)}")
by_regime = defaultdict(int)
for d in uncovered: by_regime[regimes.get(d,'?')] += 1
for r,c in sorted(by_regime.items()): print(f"    {r}: {c} days")

print("\n" + "="*65)
print("7. BEAR_TREND_FOLLOWER single loss — 2026-05-05 — what happened?")
print("="*65)
r=df[(df['strategy']=='BEAR_TREND_FOLLOWER')&(df['won']==False)].iloc[0]
print(f"  Date {str(r['date'])[:10]}  entry {r['entry_hhmm']}  exit {r['exit_reason']}  Rs{r['pnl_rs']:+,.0f}")
print(f"  Confidence: {r['confidence']:.3f}  regime: {r['regime']}")

print("\n" + "="*65)
print("8. PER-STRATEGY SL BACKSTOP — how often does SL_BACKSTOP (30%) fire?")
print("="*65)
sl_exits = df[df['exit_reason']=='SL']
print(f"  SL exits: {len(sl_exits)}")
if len(sl_exits)>0:
    for _,r in sl_exits.iterrows():
        print(f"    {r['strategy']}  Rs{r['pnl_rs']:+,.0f}")
