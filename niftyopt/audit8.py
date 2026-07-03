#!/usr/bin/env python3
"""
Diagnose why thin months have so few trades.
Check what profile conditions are blocking entry on uncovered days.
"""
import sys; sys.path.insert(0,'c:/cursor/options/niftyopt')
import pandas as pd, numpy as np
from BACKTEST_V6_PROFILED import (run_v6, load_option_data, load_eod_data,
    compute_day_context, compute_intraday_state, match_profile,
    STRATEGY_PROFILES, ACTIVE_STRATEGIES, ENTRY_START, ENTRY_CUTOFF)
from regime_detector import label_days
from BACKTEST_V3_TUNED import make_strategies

opt=load_option_data(); eod=load_eod_data()
trades=run_v6(opt,eod)
df=pd.DataFrame([t.__dict__ for t in trades])
traded=set(df['date'].unique())
regimes=label_days(opt)
all_strats={s.name:s for s in make_strategies()}

# Focus on thin months — what days were skipped and WHY
thin_months=['2025-04','2026-02','2026-03','2026-05']

print("="*65)
print("PROFILE REJECTION ANALYSIS — thin month uncovered days")
print("="*65)

# Build prev_close lookup
eod_sorted=eod.sort_values('dt') if 'dt' in eod.columns else eod.sort_values(eod.columns[0])
eod_dates=eod_sorted['dt'].values if 'dt' in eod_sorted.columns else eod_sorted.iloc[:,0].values
eod_closes=eod_sorted['close'].values if 'close' in eod_sorted.columns else eod_sorted['spot'].values

for d in sorted(opt['date'].unique()):
    month=str(d)[:7]
    if month not in thin_months: continue
    if d in traded: continue
    if regimes.get(d) not in {'TRENDING_BULL','TRENDING_BEAR','NORMAL'}: continue

    day_opt=opt[opt['date']==d]
    # find prev close
    prev_idx=np.searchsorted(eod_dates, d)-1
    prev_close=float(eod_closes[prev_idx]) if prev_idx>=0 else float(day_opt['spot'].iloc[0])

    # Build 15-min bars
    c15=day_opt.groupby(pd.Grouper(key='ts_ist',freq='15min')).agg(
        open=('spot','first'),close=('spot','last'),
        high=('spot','max'),low=('spot','min'),volume=('spot','count')).dropna()
    if len(c15)<5: continue

    # Day context
    pcr=float(day_opt['pcr'].iloc[0]) if 'pcr' in day_opt.columns else 1.0
    ctx=compute_day_context(c15,prev_close,pcr)

    print(f"\n{str(d)[:10]}  {regimes.get(d)}  gap={ctx.gap_pct:.2f}%  pcr={ctx.pcr_open:.2f}")

    # Check each active strategy profile match at bars 4-8
    for i in range(4, min(9, len(c15))):
        candles=c15.iloc[:i+1]
        state=compute_intraday_state(candles, pcr)
        ts=candles.index[i] if hasattr(candles.index[i],'hour') else pd.Timestamp(candles.index[i])
        hhmm=ts.hour*100+ts.minute

        for sname in ACTIVE_STRATEGIES:
            if sname not in STRATEGY_PROFILES: continue
            profile=STRATEGY_PROFILES[sname]
            strat=all_strats.get(sname)
            if not strat: continue

            # Check entry window
            entry_start=ENTRY_START.get(sname, strat.entry_start if hasattr(strat,'entry_start') else 930)
            entry_cut=ENTRY_CUTOFF.get(sname, strat.entry_end if hasattr(strat,'entry_end') else 1400)
            if hhmm < entry_start or hhmm > entry_cut: continue

            # Direction
            dirs=['CE'] if profile.direction=='CE' else (['PE'] if profile.direction=='PE' else ['CE','PE'])
            for direction in dirs:
                armed, conf, reason = match_profile(profile, ctx, state, direction)
                if armed:
                    print(f"  BAR {hhmm}  {sname} {direction} ARMED conf={conf:.3f}")
                    break
                # Show why rejected (only for key strategies at bar ~1100)
                if hhmm==1115 and sname in {'DAY_LOW_BULLISH','DAY_HIGH_BEARISH','BEAR_TREND_FOLLOWER','BULL_TREND_FOLLOWER'}:
                    print(f"  BAR {hhmm}  {sname} {direction} BLOCKED: {reason[:80]}")
