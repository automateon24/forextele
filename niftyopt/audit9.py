#!/usr/bin/env python3
"""
Detailed audit: winners vs losers, TIME exit breakdown per strategy,
uncovered days that the winners could catch with relaxed signal_check.
"""
import sys; sys.path.insert(0,'c:/cursor/options/niftyopt')
import pandas as pd, numpy as np
from BACKTEST_V6_PROFILED import run_v6, load_option_data, load_eod_data
from regime_detector import label_days

opt=load_option_data(); eod=load_eod_data()
trades=run_v6(opt,eod)
df=pd.DataFrame([t.__dict__ for t in trades])
df['entry_hhmm']=pd.to_datetime(df['entry_time']).apply(lambda x: x.hour*100+x.minute)
df['month']=pd.to_datetime(df['date']).dt.to_period('M')

print("="*65)
print("STRATEGY SCORECARD — WINNERS vs LOSERS")
print("="*65)
for s,g in df.groupby('strategy'):
    wins=g[g['won']==True]
    losses=g[g['won']==False]
    time_losses=g[(g['exit_reason']=='TIME')&(g['won']==False)]
    print(f"\n{'='*55}")
    print(f"  {s}")
    print(f"  Trades={len(g)}  WR={g['won'].mean()*100:.0f}%  Net=Rs{g['pnl_rs'].sum():+,.0f}  Avg=Rs{g['pnl_rs'].mean():+,.0f}")
    print(f"  Wins: {len(wins)} avg=Rs{wins['pnl_rs'].mean():+,.0f}" if len(wins) else "  Wins: 0")
    print(f"  Losses: {len(losses)} avg=Rs{losses['pnl_rs'].mean():+,.0f}" if len(losses) else "  Losses: 0")
    if len(time_losses):
        print(f"  TIME-exit losses: {len(time_losses)}  total=Rs{time_losses['pnl_rs'].sum():+,.0f}")
        for _,r in time_losses.iterrows():
            print(f"    {str(r['date'])[:10]}  entry {r['entry_hhmm']}  conf={r['confidence']:.3f}  Rs{r['pnl_rs']:+,.0f}")
    tsl_wins=g[(g['exit_reason']=='TSL')&(g['won']==True)]
    if len(tsl_wins):
        print(f"  TSL wins: {len(tsl_wins)}  avg=Rs{tsl_wins['pnl_rs'].mean():+,.0f}  "
              f"range=[Rs{tsl_wins['pnl_rs'].min():,.0f}, Rs{tsl_wins['pnl_rs'].max():,.0f}]")

print("\n\n" + "="*65)
print("MONTHLY CONSISTENCY — are we hitting 5% every month?")
print("="*65)
monthly=df.groupby('month').agg(pnl=('pnl_rs','sum'),trades=('pnl_rs','count'),wr=('won','mean'))
for _,r in monthly.reset_index().iterrows():
    flag = ' << BELOW 5k' if r['pnl'] < 5000 else ' OK'
    print(f"  {r['month']}  Rs{r['pnl']:+6,.0f}  {r['trades']:2} trades  {r['wr']*100:.0f}% WR{flag}")

print("\n\n" + "="*65)
print("UNCOVERED DAYS ANALYSIS — by month, which months are dry?")
print("="*65)
regimes=label_days(opt)
traded=set(df['date'].unique())
all_days=sorted(opt['date'].unique())
uncov=[d for d in all_days if d not in traded
       and regimes.get(d) in {'TRENDING_BULL','TRENDING_BEAR','NORMAL'}]
uncov_df=pd.DataFrame({'date':uncov,'regime':[regimes.get(d) for d in uncov]})
uncov_df['month']=pd.to_datetime(uncov_df['date']).dt.to_period('M')
print(f"  Total uncovered tradeable days: {len(uncov)}")
for m,g in uncov_df.groupby('month'):
    print(f"  {m}: {len(g)} uncovered  "
          f"BULL={( g['regime']=='TRENDING_BULL').sum()}  "
          f"BEAR={(g['regime']=='TRENDING_BEAR').sum()}  "
          f"NORM={(g['regime']=='NORMAL').sum()}")

print("\n\n" + "="*65)
print("BEAR_TREND + BULL_TREND — TIME exit root cause")
print("="*65)
trend_time=df[(df['strategy'].isin(['BEAR_TREND_FOLLOWER','BULL_TREND_FOLLOWER']))
              &(df['exit_reason']=='TIME')].copy()
for _,r in trend_time.iterrows():
    print(f"  {str(r['date'])[:10]}  {r['strategy'][:16]}  {r['direction']}  "
          f"entry {r['entry_hhmm']}  conf={r['confidence']:.3f}  "
          f"regime={r['regime']}  Rs{r['pnl_rs']:+,.0f}")

print("\n\n" + "="*65)
print("DAY_LOW_BULLISH — only loser: 2025-03-07. Why?")
print("="*65)
dlb=df[df['strategy']=='DAY_LOW_BULLISH']
losses_dlb=dlb[dlb['won']==False]
for _,r in losses_dlb.iterrows():
    print(f"  {str(r['date'])[:10]}  entry {r['entry_hhmm']}  {r['exit_reason']}  conf={r['confidence']:.3f}  Rs{r['pnl_rs']:+,.0f}")
