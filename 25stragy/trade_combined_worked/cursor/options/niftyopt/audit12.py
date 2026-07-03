#!/usr/bin/env python3
"""Audit WIDE_RANGE_RIDER and ORDER_BLOCK_REVERSAL entry times + TIME exit analysis."""
import sys; sys.path.insert(0,'c:/cursor/options/niftyopt')
import pandas as pd
from BACKTEST_V6_PROFILED import run_v6, load_option_data, load_eod_data
import BACKTEST_V6_PROFILED as bk

# Open wide for WRR to see all time buckets
orig = bk.ENTRY_CUTOFF.get('WIDE_RANGE_RIDER')
bk.ENTRY_CUTOFF['WIDE_RANGE_RIDER'] = 1400

opt=load_option_data(); eod=load_eod_data()
trades=run_v6(opt,eod)
df=pd.DataFrame([t.__dict__ for t in trades])
df['entry_hhmm']=pd.to_datetime(df['entry_time']).apply(lambda x: x.hour*100+x.minute)

print("WIDE_RANGE_RIDER — all trades by entry time:")
wrr=df[df['strategy']=='WIDE_RANGE_RIDER'].sort_values('entry_hhmm')
for _,r in wrr.iterrows():
    print(f"  {str(r['date'])[:10]}  entry {r['entry_hhmm']}  {r['exit_reason']}  "
          f"won={r['won']}  Rs{r['pnl_rs']:+,.0f}")

print("\nWIDE_RANGE_RIDER summary by bucket:")
bins=[1045,1100,1115,1130,1200,1215,1230,1300,1400]
labels=['10:45','11:00','11:15','11:30','12:00','12:15','12:30','13:00']
wrr2=wrr.copy(); wrr2['bucket']=pd.cut(wrr2['entry_hhmm'],bins=bins,labels=labels)
for b,g in wrr2.groupby('bucket',observed=True):
    if len(g)>0:
        wins=g['won'].sum(); n=len(g)
        print(f"  {b}: {n} trades  {wins}/{n} WR={wins/n*100:.0f}%  Rs{g['pnl_rs'].sum():+,.0f}")

print("\nTIME exits for WIDE_RANGE_RIDER:")
te=wrr[wrr['exit_reason']=='TIME']
for _,r in te.iterrows():
    print(f"  {str(r['date'])[:10]}  entry {r['entry_hhmm']}  regime={r['regime']}  Rs{r['pnl_rs']:+,.0f}")

print("\nORDER_BLOCK_REVERSAL — all trades:")
obr=df[df['strategy']=='ORDER_BLOCK_REVERSAL']
for _,r in obr.iterrows():
    print(f"  {str(r['date'])[:10]}  entry {r['entry_hhmm']}  {r['exit_reason']}  "
          f"won={r['won']}  Rs{r['pnl_rs']:+,.0f}")

print("\nENHANCED_BEARISH — all trades:")
eb=df[df['strategy']=='ENHANCED_BEARISH']
print(f"  Total: {len(eb)} trades")
for _,r in eb.iterrows():
    print(f"  {str(r['date'])[:10]}  entry {r['entry_hhmm']}  {r['exit_reason']}  "
          f"won={r['won']}  Rs{r['pnl_rs']:+,.0f}")
