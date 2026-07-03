#!/usr/bin/env python3
"""
Find the best new signal on uncovered days.
Analyze each uncovered day's 15min candles and identify what pattern
a new strategy could capture.
"""
import sys; sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd, numpy as np
from BACKTEST_V6_PROFILED import run_v6, load_option_data, load_eod_data
from regime_detector import label_days
from BACKTEST_V3_TUNED import calc_rsi

opt = load_option_data()
eod = load_eod_data()
trades = run_v6(opt, eod)
df = pd.DataFrame([t.__dict__ for t in trades])
regimes = label_days(opt)

all_days = sorted(opt['date'].unique())
traded_days = set(df['date'].unique())
uncovered = [d for d in all_days
             if d not in traded_days and regimes.get(d) in {'TRENDING_BULL','TRENDING_BEAR','NORMAL'}]

print(f"Uncovered tradeable days: {len(uncovered)}")
print("\nAnalyzing each uncovered day for catchable patterns...")
print("="*70)

eod_data = eod.set_index('dt') if 'dt' in eod.columns else eod

results = []
for d in uncovered:
    day_opt = opt[opt['date']==d]
    if day_opt.empty: continue
    c15 = day_opt.groupby(pd.Grouper(key='ts_ist', freq='15min')).agg(
        open=('spot','first'), close=('spot','last'),
        high=('spot','max'), low=('spot','min'), volume=('spot','count')
    ).dropna()
    if len(c15) < 5: continue

    regime  = regimes.get(d,'?')
    closes  = c15['close'].values.astype(float)
    highs   = c15['high'].values.astype(float)
    lows    = c15['low'].values.astype(float)

    day_open  = float(c15.iloc[0]['open']) if 'open' in c15.columns else float(closes[0])
    day_close = float(closes[-1])
    day_high  = float(highs.max())
    day_low   = float(lows.min())
    day_range = day_high - day_low
    direction = 'UP' if day_close > day_open else 'DOWN'

    # RSI and EMA at key points
    rsi_early = calc_rsi(closes[:4]) if len(closes) >= 4 else 50
    rsi_mid   = calc_rsi(closes[:8]) if len(closes) >= 8 else 50
    ema5_end  = float(pd.Series(closes).ewm(span=5, adjust=False).mean().iloc[-1])
    ema20_end = float(pd.Series(closes).ewm(span=20, adjust=False).mean().iloc[-1])

    # First-hour stats (first 4 bars = ~1hr)
    first_hr_high = float(highs[:4].max()) if len(highs) >= 4 else day_high
    first_hr_low  = float(lows[:4].min())  if len(lows)  >= 4 else day_low

    # Did market break first-hour high/low by 11:00?
    if len(closes) >= 4:
        broke_high = day_high > first_hr_high * 1.001
        broke_low  = day_low  < first_hr_low  * 0.999
    else:
        broke_high = broke_low = False

    # VWAP at midday bar
    above_vwap = direction == 'UP'  # simplified proxy

    results.append({
        'date': d, 'regime': regime, 'direction': direction,
        'day_range': round(day_range), 'day_open': round(day_open),
        'day_close': round(day_close),
        'rsi_early': round(rsi_early, 1), 'rsi_mid': round(rsi_mid, 1),
        'ema_bull': ema5_end > ema20_end,
        'broke_high': broke_high, 'broke_low': broke_low,
        'above_vwap': above_vwap,
        'first_hr_range': round(first_hr_high - first_hr_low),
        'gap_pct': round((day_open - float(closes[0])) / day_open * 100, 2) if len(closes) > 0 else 0,
    })

rdf = pd.DataFrame(results)

print("\n1. REGIME BREAKDOWN OF UNCOVERED DAYS:")
for regime in ['TRENDING_BULL','TRENDING_BEAR','NORMAL']:
    sub = rdf[rdf['regime']==regime]
    up = (sub['direction']=='UP').sum()
    down = (sub['direction']=='DOWN').sum()
    print(f"   {regime:<18}  {len(sub)} days  UP={up} DOWN={down}  "
          f"avg_range={sub['day_range'].mean():.0f}")

print("\n2. UNCOVERED TRENDING_BEAR DOWN DAYS (best opportunity for PE):")
bear_down = rdf[(rdf['regime']=='TRENDING_BEAR') & (rdf['direction']=='DOWN')]
print(f"   Count: {len(bear_down)}  avg_range={bear_down['day_range'].mean():.0f}")
for _, r in bear_down.iterrows():
    print(f"   {str(r['date'])[:10]}  range={r['day_range']}  "
          f"rsi_early={r['rsi_early']}  ema_bull={r['ema_bull']}  "
          f"broke_low={r['broke_low']}  above_vwap={r['above_vwap']}")

print("\n3. WHAT SIGNALS WOULD HAVE FIRED ON UNCOVERED DAYS?")
# Test: GAP_DOWN_BEAR signal — gap down day, confirm below first hour low, take PE
potential = rdf[
    (rdf['direction']=='DOWN') &
    (rdf['broke_low']==True) &
    (rdf['rsi_early'] > 40) &     # RSI not yet exhausted when breaking
    (rdf['day_range'] > 100)
]
print(f"   'GAP_DOWN_BEAR' potential: {len(potential)} days")
print(f"   Regime split:")
for regime, g in potential.groupby('regime'):
    print(f"     {regime}: {len(g)} days  avg_range={g['day_range'].mean():.0f}")

# Test: FLAT_OPEN_BULL — flat open, market trends UP with RSI building
pot_bull = rdf[
    (rdf['direction']=='UP') &
    (rdf['broke_high']==True) &
    (rdf['rsi_early'] < 60) &
    (rdf['above_vwap']==True) &
    (rdf['day_range'] > 100)
]
print(f"\n   'FLAT_OPEN_BULL' potential: {len(pot_bull)} days")
for regime, g in pot_bull.groupby('regime'):
    print(f"     {regime}: {len(g)} days  avg_range={g['day_range'].mean():.0f}")

print("\n4. WHAT'S THE MAX POTENTIAL IF WE CAUGHT UNCOVERED DAYS?")
# Assume avg TSL win = 726 if we caught 1 trade per uncovered day at 70% WR
n_uncovered = len(uncovered)
avg_tsl_win = 726
avg_tsl_loss = -400
wr_assumed = 0.70
expected = n_uncovered * (wr_assumed * avg_tsl_win + (1-wr_assumed) * avg_tsl_loss)
print(f"   {n_uncovered} uncovered days × (70%×₹726 + 30%×-₹400) = ₹{expected:+,.0f} additional")
print(f"   Combined with current ₹28,157 → ₹{28157+expected:+,.0f} total")

print("\n5. CURRENT TIME EXITS — remaining 19:")
time_df = df[df['exit_reason']=='TIME'].copy()
time_df['entry_hhmm'] = pd.to_datetime(time_df['entry_time']).apply(lambda x: x.hour*100+x.minute)
for _, r in time_df.iterrows():
    print(f"   {str(r['date'])[:10]}  {r['strategy'][:20]}  {r['direction']}  "
          f"entry {r['entry_hhmm']}  {r['regime']:<15}  Rs{r['pnl_rs']:+,.0f}")
