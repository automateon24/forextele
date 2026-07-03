#!/usr/bin/env python3
"""Analyze HIGH_VOLATILITY days and NORMAL DOWN days."""
import sys; sys.path.insert(0,'c:/cursor/options/niftyopt')
import pandas as pd, numpy as np
from BACKTEST_V6_PROFILED import run_v6, load_option_data, load_eod_data
from regime_detector import label_days
from BACKTEST_V3_TUNED import calc_rsi

opt=load_option_data(); eod=load_eod_data()
regimes=label_days(opt)
all_days=sorted(opt['date'].unique())

hv_days=[d for d in all_days if regimes.get(d)=='HIGH_VOLATILITY']
print(f"HIGH_VOLATILITY days in dataset: {len(hv_days)}")

results=[]
for d in hv_days:
    day_opt=opt[opt['date']==d]
    c15=day_opt.groupby(pd.Grouper(key='ts_ist',freq='15min')).agg(
        open=('spot','first'),close=('spot','last'),
        high=('spot','max'),low=('spot','min')).dropna()
    if len(c15)<5: continue
    o=float(c15.iloc[0]['open']); cl=float(c15.iloc[-1]['close'])
    rng=float(c15['high'].max())-float(c15['low'].min())
    direction='UP' if cl>o else 'DOWN'
    closes=c15['close'].values.astype(float)
    ema5=float(pd.Series(closes).ewm(span=5,adjust=False).mean().iloc[-1])
    ema20=float(pd.Series(closes).ewm(span=20,adjust=False).mean().iloc[-1])
    rsi_end=calc_rsi(closes)
    results.append({'date':d,'direction':direction,'range':rng,
                    'open':round(o),'close':round(cl),
                    'ema_bull':ema5>ema20,'rsi_end':round(rsi_end,1)})

rdf=pd.DataFrame(results)
print(f"UP: {(rdf['direction']=='UP').sum()}  DOWN: {(rdf['direction']=='DOWN').sum()}")
print(f"Avg range: {rdf['range'].mean():.0f}  Min: {rdf['range'].min():.0f}  Max: {rdf['range'].max():.0f}")
print(f"Range >200pts (tradeable): {(rdf['range']>200).sum()}")
print(f"Range >150pts: {(rdf['range']>150).sum()}")
print(f"\nMonthly breakdown:")
rdf['month']=pd.to_datetime(rdf['date']).dt.to_period('M')
for m,g in rdf.groupby('month'):
    print(f"  {m}: {len(g)} HV days  UP={( g['direction']=='UP').sum()} DOWN={(g['direction']=='DOWN').sum()}  avg_range={g['range'].mean():.0f}")

print(f"\nSample HV days:")
for _,r in rdf.sample(min(10,len(rdf)),random_state=42).sort_values('date').iterrows():
    print(f"  {str(r['date'])[:10]}  {r['direction']}  range={r['range']:.0f}  rsi={r['rsi_end']}  ema_bull={r['ema_bull']}")

print("\n" + "="*60)
print("NORMAL DOWN uncovered days — can MEAN_REVERSION catch them?")
print("="*60)
trades=run_v6(opt,eod)
df=pd.DataFrame([t.__dict__ for t in trades])
traded=set(df['date'].unique())

norm_down=[d for d in all_days if d not in traded
           and regimes.get(d)=='NORMAL']
print(f"NORMAL uncovered: {len(norm_down)} days")
print("What was happening intraday on these days (first 4 15min bars):")
for d in norm_down[:10]:
    day_opt=opt[opt['date']==d]
    c15=day_opt.groupby(pd.Grouper(key='ts_ist',freq='15min')).agg(
        open=('spot','first'),close=('spot','last'),
        high=('spot','max'),low=('spot','min')).dropna()
    if len(c15)<5: continue
    closes=c15['close'].values.astype(float)
    rsi_early=calc_rsi(closes[:4])
    rsi_mid=calc_rsi(closes[:8]) if len(closes)>=8 else 50
    o=float(c15.iloc[0]['open']); cl=float(c15.iloc[-1]['close'])
    rng=float(c15['high'].max())-float(c15['low'].min())
    ema5=float(pd.Series(closes[:6]).ewm(span=5,adjust=False).mean().iloc[-1])
    ema20=float(pd.Series(closes[:6]).ewm(span=20,adjust=False).mean().iloc[-1])
    direction='UP' if cl>o else 'DOWN'
    print(f"  {str(d)[:10]}  {direction}  range={rng:.0f}  "
          f"rsi_early={rsi_early:.0f}  rsi_mid={rsi_mid:.0f}  "
          f"ema_bull={ema5>ema20}")
