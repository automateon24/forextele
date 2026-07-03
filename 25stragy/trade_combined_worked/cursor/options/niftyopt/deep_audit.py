#!/usr/bin/env python3
"""
Deep audit: Find every leak and opportunity in V6 results.
1. What are the TIME exit days — what pattern caused them?
2. What are the best TSL days — what conditions made them fire?
3. DAY_HIGH_BEARISH has 30 trades at only 60% WR — audit each loss
4. MEAN_REVERSION fires twice same day (2026-01-13 = -2296) — when does double-fire hurt?
5. What is the TRUE best entry time per strategy from actual trades?
"""
import sys; sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd
import numpy as np
from collections import defaultdict
from BACKTEST_V6_PROFILED import run_v6, load_option_data, load_eod_data

print("Loading data...")
opt = load_option_data()
eod = load_eod_data()
print("Running backtest...")
trades = run_v6(opt, eod)
df = pd.DataFrame([t.__dict__ for t in trades])
df['entry_hhmm'] = pd.to_datetime(df['entry_time']).apply(lambda x: x.hour*100+x.minute)
df['exit_hhmm']  = pd.to_datetime(df['exit_time']).apply(lambda x: x.hour*100+x.minute if pd.notnull(x) else 9999)

print("\n" + "="*70)
print("1. TIME EXIT DEEP AUDIT — why are 28 trades timing out?")
print("="*70)
time_df = df[df['exit_reason']=='TIME'].copy()
print(f"   Total TIME exits: {len(time_df)}, Total loss: ₹{time_df['pnl_rs'].sum():+,.0f}")
print(f"   Avg loss per TIME exit: ₹{time_df['pnl_rs'].mean():+,.0f}")
print(f"\n   TIME exits by strategy:")
for s, g in time_df.groupby('strategy'):
    print(f"     {s:<25} {len(g):>3} trades  ₹{g['pnl_rs'].sum():+7,.0f}  "
          f"entry: {g['entry_hhmm'].min()}-{g['entry_hhmm'].max()}")

print(f"\n   TIME exit entry time distribution:")
bins = [930,1000,1030,1100,1130,1200,1230,1300,1330,1400,1415]
labels = ['9:30','10:00','10:30','11:00','11:30','12:00','12:30','13:00','13:30','14:00']
time_df['entry_bucket'] = pd.cut(time_df['entry_hhmm'], bins=bins, labels=labels)
for bucket, g in time_df.groupby('entry_bucket', observed=True):
    print(f"     Entered {bucket}:  {len(g)} TIME exits, avg PnL ₹{g['pnl_rs'].mean():+,.0f}")

print("\n" + "="*70)
print("2. DAY_HIGH_BEARISH LOSS AUDIT — 30 trades, 60% WR = 12 losses")
print("="*70)
dhb = df[df['strategy']=='DAY_HIGH_BEARISH'].copy()
losses = dhb[dhb['won']==False]
wins   = dhb[dhb['won']==True]
print(f"   Wins:   {len(wins):>3}  avg ₹{wins['pnl_rs'].mean():+,.0f}  "
      f"entry range {wins['entry_hhmm'].min()}-{wins['entry_hhmm'].max()}")
print(f"   Losses: {len(losses):>3}  avg ₹{losses['pnl_rs'].mean():+,.0f}  "
      f"entry range {losses['entry_hhmm'].min()}-{losses['entry_hhmm'].max()}")
print(f"\n   Loss detail (regime + exit reason):")
for _, r in losses.iterrows():
    print(f"     {str(r['date'])[:10]}  entry {r['entry_hhmm']}  {r['regime']:<15}  "
          f"{r['exit_reason']:<6}  ₹{r['pnl_rs']:+,.0f}")

print(f"\n   WR by entry time bucket for DAY_HIGH_BEARISH:")
dhb['entry_bucket'] = pd.cut(dhb['entry_hhmm'], bins=bins, labels=labels)
for bucket, g in dhb.groupby('entry_bucket', observed=True):
    if len(g) > 0:
        wr = g['won'].mean()*100
        print(f"     Entered {bucket}:  {len(g)} trades  {wr:.0f}% WR  ₹{g['pnl_rs'].sum():+,.0f}")

print("\n" + "="*70)
print("3. MEAN_REVERSION DOUBLE-FIRE AUDIT")
print("="*70)
mr = df[df['strategy']=='MEAN_REVERSION'].copy()
day_counts = mr.groupby('date').size()
double_days = day_counts[day_counts >= 2].index
print(f"   Days with 2+ MR trades: {len(double_days)}")
for day in double_days:
    day_trades = mr[mr['date']==day]
    total = day_trades['pnl_rs'].sum()
    detail = '  '.join([f"{r['direction']} {r['exit_reason']} ₹{r['pnl_rs']:+,.0f}"
                        for _, r in day_trades.iterrows()])
    print(f"     {str(day)[:10]}  total ₹{total:+,.0f}  |  {detail}")

print(f"\n   Single MR trade days: {(day_counts==1).sum()}  avg ₹{mr[mr['date'].isin(day_counts[day_counts==1].index)]['pnl_rs'].mean():+,.0f}")
print(f"   Double MR trade days: {(day_counts>=2).sum()}  avg ₹{mr[mr['date'].isin(double_days)].groupby('date')['pnl_rs'].sum().mean():+,.0f}")

print("\n" + "="*70)
print("4. TREND_FOLLOWING AUDIT — 3 trades 33% WR")
print("="*70)
tf = df[df['strategy']=='TREND_FOLLOWING']
for _, r in tf.iterrows():
    print(f"   {str(r['date'])[:10]}  {r['direction']}  entry {r['entry_hhmm']}  "
          f"{r['regime']:<15}  {r['exit_reason']}  ₹{r['pnl_rs']:+,.0f}")

print("\n" + "="*70)
print("5. BEST PERFORMING DAYS — what conditions made them great?")
print("="*70)
daily = df.groupby('date').agg(total=('pnl_rs','sum'), trades=('pnl_rs','count'),
                                wr=('won','mean')).sort_values('total', ascending=False)
print("   Top 10 days:")
for day, row in daily.head(10).iterrows():
    day_trades = df[df['date']==day]
    strats = '+'.join([f"{r['strategy'][:8]}({r['direction']})" for _, r in day_trades.iterrows()])
    print(f"     {str(day)[:10]}  ₹{row['total']:+,.0f}  {row['trades']} trades  {strats}")

print("\n" + "="*70)
print("6. REGIME OPPORTUNITY AUDIT — what regimes have lots of uncovered days?")
print("="*70)
from regime_detector import label_days
regimes = label_days(opt)
all_days = sorted(opt['date'].unique())
traded_days = set(df['date'].unique())
for regime in ['TRENDING_BULL','TRENDING_BEAR','NORMAL']:
    regime_days = [d for d in all_days if regimes.get(d)==regime]
    covered = [d for d in regime_days if d in traded_days]
    uncovered = [d for d in regime_days if d not in traded_days]
    print(f"   {regime:<18}  total={len(regime_days)}  traded={len(covered)}  "
          f"UNCOVERED={len(uncovered)}")
    if uncovered and len(uncovered) <= 10:
        for d in uncovered[:5]:
            print(f"     {str(d)[:10]} — no signal fired")

print("\n" + "="*70)
print("7. EXIT QUALITY — how much are we leaving on table?")
print("="*70)
tsl_df = df[df['exit_reason']=='TSL']
print(f"   TSL exits: {len(tsl_df)}")
print(f"   Avg TSL gain: ₹{tsl_df['pnl_rs'].mean():+,.0f}")
print(f"   Best TSL: ₹{tsl_df['pnl_rs'].max():+,.0f}")
print(f"   TSL by strategy:")
for s, g in tsl_df.groupby('strategy'):
    print(f"     {s:<25} {len(g):>2} trades  avg ₹{g['pnl_rs'].mean():+,.0f}  max ₹{g['pnl_rs'].max():+,.0f}")

print("\n" + "="*70)
print("8. SL_PCT SENSITIVITY — could tighter SL reduce TIME exit losses?")
print("="*70)
print("   TIME exits pnl_pts distribution (how far down before time exit):")
time_pts = df[df['exit_reason']=='TIME']['pnl_pts']
for pct in [25, 50, 75]:
    print(f"     {pct}th percentile: {time_pts.quantile(pct/100):.1f} pts")
print(f"   If we cut TIME exits where pnl_pts < -15: saves "
      f"₹{df[(df['exit_reason']=='TIME') & (df['pnl_pts']<-15)]['pnl_rs'].sum()*-1:+,.0f}")
