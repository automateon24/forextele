#!/usr/bin/env python3
import sys; sys.path.insert(0,'c:/cursor/options/niftyopt')
import pandas as pd
from BACKTEST_V6_PROFILED import run_v6, load_option_data, load_eod_data
opt=load_option_data(); eod=load_eod_data()
trades=run_v6(opt,eod)
df=pd.DataFrame([t.__dict__ for t in trades])
df['entry_hhmm']=pd.to_datetime(df['entry_time']).apply(lambda x: x.hour*100+x.minute)
bins=[1000,1030,1100,1130,1200,1230,1300]
labels=['10:00','10:30','11:00','11:30','12:00','12:30']

print("BULL_TREND_FOLLOWER by entry time:")
btf=df[df['strategy']=='BULL_TREND_FOLLOWER'].copy()
btf['bucket']=pd.cut(btf['entry_hhmm'],bins=bins,labels=labels)
for b,g in btf.groupby('bucket',observed=True):
    wr = g['won'].mean()*100
    print(f"  {b}: {len(g)} trades  {wr:.0f}% WR  Rs{g['pnl_rs'].sum():+,.0f}")

print("\nBEAR_TREND_FOLLOWER by entry time:")
beartf=df[df['strategy']=='BEAR_TREND_FOLLOWER'].copy()
beartf['bucket']=pd.cut(beartf['entry_hhmm'],bins=bins,labels=labels)
for b,g in beartf.groupby('bucket',observed=True):
    wr = g['won'].mean()*100
    print(f"  {b}: {len(g)} trades  {wr:.0f}% WR  Rs{g['pnl_rs'].sum():+,.0f}")

print("\nBULL_TREND_FOLLOWER all trades detail:")
for _,r in btf.iterrows():
    print(f"  {str(r['date'])[:10]}  entry {r['entry_hhmm']}  {r['exit_reason']}  won={r['won']}  Rs{r['pnl_rs']:+,.0f}")

print("\nBEAR_TREND_FOLLOWER losses detail:")
for _,r in beartf[beartf['won']==False].iterrows():
    print(f"  {str(r['date'])[:10]}  entry {r['entry_hhmm']}  {r['exit_reason']}  Rs{r['pnl_rs']:+,.0f}")
