import sys, os, pandas as pd, numpy as np
sys.path.insert(0, 'c:/cursor/options/niftyopt')

from BACKTEST_V3_TUNED import make_strategies, signal_check, build_15min_spot, calc_pcr
from BACKTEST_V6_PROFILED import (
    ACTIVE_STRATEGIES, STRATEGY_PROFILES, TRADEABLE_REGIMES,
    compute_day_context, compute_intraday_state, match_profile, ENTRY_START, ENTRY_CUTOFF
)
from regime_detector import label_days

UTC_OFFSET = pd.Timedelta(hours=5, minutes=30)
RAW_DIR = 'data/raw'

# ── 1. Show strat.strike values ─────────────────────────────────────────────
strats = make_strategies()
active = [s for s in strats if s.name in ACTIVE_STRATEGIES]
print('=== ACTIVE STRATEGY STRIKES ===')
for s in active:
    print(f'  {s.name:30s}  strike={repr(s.strike):10s}  dir={s.direction}')

# ── 2. Load a single BN day and trace why signals don't fire ────────────────
import glob, re
pqs = sorted(glob.glob(os.path.join(RAW_DIR, 'BANKNIFTY_expired_*.parquet')))
frames = []
for p in pqs:
    df = pd.read_parquet(p)
    bn = os.path.basename(p)
    df['option_type_flag'] = 'CE' if 'CALL' in bn else 'PE'
    ts = pd.to_datetime(df['timestamp'])
    if ts.dt.tz is not None:
        ts = ts.dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
    elif ts.dt.hour.median() <= 7:
        ts = ts + UTC_OFFSET
    df['timestamp'] = ts
    frames.append(df)

data = pd.concat(frames, ignore_index=True)
data['ts_ist'] = pd.to_datetime(data['timestamp'])
data['date']   = data['ts_ist'].dt.date
data['hhmm']   = data['ts_ist'].dt.hour * 100 + data['ts_ist'].dt.minute
data = data.sort_values(['date','strike','option_type_flag','ts_ist']).reset_index(drop=True)

print(f'\n=== BN DATA: {len(data)} rows, {data.date.nunique()} days ===')
print(f'strike column unique: {sorted(data.strike.unique())}')
print(f'option_type_flag unique: {sorted(data.option_type_flag.unique())}')

# Pick a specific day to trace
sample_day = sorted(data.date.unique())[10]
print(f'\n=== TRACING DAY: {sample_day} ===')
day_data = data[data['date'] == sample_day].copy()

# Show what ATM CE and PE look like at a signal time
atm_ce = day_data[(day_data['strike']=='ATM') & (day_data['option_type_flag']=='CE')]
print(f'ATM CE rows for day: {len(atm_ce)}')
if len(atm_ce) > 0:
    print(atm_ce[['hhmm','open','high','low','close','spot']].head(10).to_string())

# ── 3. Build c15 and run regime + profile matching ──────────────────────────
day_regimes = label_days(data)
regime = day_regimes.get(sample_day, 'NORMAL')
print(f'\nRegime for {sample_day}: {regime}')
print(f'Tradeable: {regime in TRADEABLE_REGIMES}')

c15 = build_15min_spot(day_data)
print(f'c15 rows built: {len(c15)}')
if len(c15) > 0:
    print(c15[['open','high','low','close']].head(8).to_string())

# PCR
pcr = calc_pcr(day_data)
print(f'PCR: {pcr:.3f}')

# prev_close
prev_days = sorted([d for d in data.date.unique() if d < sample_day])
if prev_days:
    prev_day = prev_days[-1]
    prev_data = data[(data['date']==prev_day) & (data['option_type_flag']=='CE') & (data['strike']=='ATM')]
    prev_close = float(prev_data.spot.iloc[-1]) if len(prev_data) > 0 else 0.0
else:
    prev_close = 0.0
print(f'prev_close: {prev_close:.0f}')

# Try profile matching at each 15min bar
print(f'\n=== PROFILE MATCH TRACE (BN day={sample_day}) ===')
if len(c15) >= 4:
    for i in range(3, min(len(c15), 20)):
        row  = c15.iloc[i]
        hhmm = int(row.get('hhmm', 0)) if 'hhmm' in c15.columns else 0
        
        ctx   = compute_day_context(c15.iloc[:i+1], prev_close, pcr)
        state = compute_intraday_state(c15.iloc[:i+1], pcr)
        
        for strat in active[:4]:  # check first 4 strats
            entry_start = ENTRY_START.get(strat.name, strat.entry_start)
            entry_cut   = ENTRY_CUTOFF.get(strat.name, strat.entry_end)
            
            if strat.name not in STRATEGY_PROFILES:
                continue
            profile = STRATEGY_PROFILES[strat.name]
            
            dirs = ['CE','PE'] if strat.direction == 'BOTH' else [strat.direction]
            for direction in dirs:
                armed, conf, reason = match_profile(profile, ctx, state, direction)
                if armed:
                    print(f'  bar {i} hhmm={hhmm} strat={strat.name} dir={direction} ARMED conf={conf:.2f}')
                    # Now check if opt_b lookup would work
                    opt_b = day_data[
                        (day_data['option_type_flag'] == direction) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] == hhmm)
                    ]
                    print(f'    opt_b lookup (strike={strat.strike}, hhmm={hhmm}): {len(opt_b)} rows')
                    if len(opt_b) == 0:
                        # what strikes/hhmm ARE available?
                        avail = day_data[(day_data['option_type_flag']==direction)]['strike'].unique()
                        avail_hhmm = day_data[(day_data['option_type_flag']==direction)&(day_data['strike']=='ATM')]['hhmm'].unique()
                        print(f'    available strikes: {sorted(avail)}')
                        print(f'    ATM hhmm range: {min(avail_hhmm) if len(avail_hhmm)>0 else "none"} to {max(avail_hhmm) if len(avail_hhmm)>0 else "none"}')
                else:
                    if i == 8:  # show one rejection reason
                        print(f'  bar {i} strat={strat.name} dir={direction} BLOCKED: {reason}  ctx_gap={ctx.gap_pct:.2f} ctx_pcr={ctx.pcr_open:.2f} state_rsi={state.rsi:.1f} range_cons={state.range_consumed:.2f}')

# ── 4. Count how many bars per day actually have ATM CE data ────────────────
print(f'\n=== ATM CE HHMM coverage across ALL BN days ===')
atm_all = data[(data['strike']=='ATM')&(data['option_type_flag']=='CE')]
print(f'Total ATM CE rows: {len(atm_all)}')
hhmm_counts = atm_all.groupby('hhmm').size()
print(f'hhmm coverage: {hhmm_counts[hhmm_counts.index.isin([930,945,1000,1015,1100,1200,1300,1400,1415])].to_dict()}')

# Check how many days have ATM CE data at 1200-1400
days_with_atm = atm_all[atm_all['hhmm'].between(1200,1400)]['date'].nunique()
print(f'Days with ATM CE data in 12:00-14:00: {days_with_atm}')
