#!/usr/bin/env python3
"""Find exact entry times for DAY_HIGH_BEARISH and DAY_LOW_BULLISH wins vs losses."""
import sys; sys.path.insert(0,'c:/cursor/options/niftyopt')
import pandas as pd
from BACKTEST_V6_PROFILED import run_v6, load_option_data, load_eod_data

# Temporarily set cutoffs wide to see all historical trades
import BACKTEST_V6_PROFILED as bk
orig_dhb = bk.ENTRY_CUTOFF.get('DAY_HIGH_BEARISH')
orig_dlb = bk.ENTRY_CUTOFF.get('DAY_LOW_BULLISH')
bk.ENTRY_CUTOFF['DAY_HIGH_BEARISH'] = 1400
bk.ENTRY_CUTOFF['DAY_LOW_BULLISH']  = 1400

opt=load_option_data(); eod=load_eod_data()
trades=run_v6(opt,eod)
df=pd.DataFrame([t.__dict__ for t in trades])
df['entry_hhmm']=pd.to_datetime(df['entry_time']).apply(lambda x: x.hour*100+x.minute)

print("DAY_HIGH_BEARISH — all trades by entry time:")
dhb=df[df['strategy']=='DAY_HIGH_BEARISH'].sort_values('entry_hhmm')
for _,r in dhb.iterrows():
    print(f"  {str(r['date'])[:10]}  entry {r['entry_hhmm']}  {r['exit_reason']}  "
          f"won={r['won']}  Rs{r['pnl_rs']:+,.0f}")

print("\nDAY_HIGH_BEARISH summary by 15-min bucket:")
bins=[1230,1245,1300,1315,1330,1345,1400,1415]
labels=['12:30','12:45','13:00','13:15','13:30','13:45','14:00']
dhb2=dhb.copy(); dhb2['bucket']=pd.cut(dhb2['entry_hhmm'],bins=bins,labels=labels)
for b,g in dhb2.groupby('bucket',observed=True):
    if len(g)>0:
        print(f"  {b}: {len(g)} trades  {g['won'].mean()*100:.0f}% WR  Rs{g['pnl_rs'].sum():+,.0f}")

print("\nDAY_LOW_BULLISH — all trades by entry time:")
dlb=df[df['strategy']=='DAY_LOW_BULLISH'].sort_values('entry_hhmm')
for _,r in dlb.iterrows():
    print(f"  {str(r['date'])[:10]}  entry {r['entry_hhmm']}  {r['exit_reason']}  "
          f"won={r['won']}  Rs{r['pnl_rs']:+,.0f}")

print("\nDAY_LOW_BULLISH summary by bucket:")
bins2=[930,1000,1030,1100,1130,1200,1230,1300,1330,1400]
labels2=['09:30','10:00','10:30','11:00','11:30','12:00','12:30','13:00','13:30']
dlb2=dlb.copy(); dlb2['bucket']=pd.cut(dlb2['entry_hhmm'],bins=bins2,labels=labels2)
for b,g in dlb2.groupby('bucket',observed=True):
    if len(g)>0:
        print(f"  {b}: {len(g)} trades  {g['won'].mean()*100:.0f}% WR  Rs{g['pnl_rs'].sum():+,.0f}")
