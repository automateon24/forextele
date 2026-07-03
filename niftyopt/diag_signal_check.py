"""
Trace why signal_check fails 874 times for BANKNIFTY.
Also check premium scale issues.
"""
import sys, os, pandas as pd, numpy as np, glob
sys.path.insert(0, 'c:/cursor/options/niftyopt')

from BACKTEST_V3_TUNED import (
    make_strategies, signal_check, build_15min_spot, calc_pcr, PERIODS, STRIKES, OPT_TYPES
)
from BACKTEST_V6_PROFILED import (
    ACTIVE_STRATEGIES, TRADEABLE_REGIMES,
    compute_day_context, compute_intraday_state, match_profile,
    ENTRY_START, ENTRY_CUTOFF
)
from BACKTEST_V7_MULTIINDEX import INDEX_PROFILES, INDEX_CONFIGS
from regime_detector import label_days

UTC_OFFSET = pd.Timedelta(hours=5, minutes=30)
RAW_DIR    = 'data/raw'
IDX        = 'BANKNIFTY'

# ── Load data ────────────────────────────────────────────────────────────────
print(f'Loading {IDX}...')
frames = []
for ps, pe in PERIODS:
    for strike in STRIKES:
        for otype in OPT_TYPES:
            fname = f"{IDX}_expired_{ps}_{pe}_{strike}_{otype}_1min_MONTH_1.parquet"
            fpath = os.path.join(RAW_DIR, fname)
            if not os.path.exists(fpath):
                continue
            df = pd.read_parquet(fpath)
            df['option_type_flag'] = 'CE' if otype == 'CALL' else 'PE'
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

cfg          = INDEX_CONFIGS[IDX]
idx_profiles = INDEX_PROFILES[IDX]
active_strats = [s for s in make_strategies() if s.name in ACTIVE_STRATEGIES]
day_regimes   = label_days(data)
trading_days  = sorted(data['date'].unique())

ce_spot = data[data['option_type_flag']=='CE'][['date','spot']].copy()
eod_data = ce_spot.groupby('date').agg(
    open=('spot','first'), high=('spot','max'),
    low=('spot','min'),  close=('spot','last')
).reset_index().rename(columns={'date':'dt'})

from collections import defaultdict

# ── Instrument signal_check to see WHY it fails ──────────────────────────────
# Look at what signal_check checks internally for BN
# First, let's look at what arguments it receives vs what it rejects

signal_fail_details = []
signal_pass_details = []
prev_close = 0.0

for day in trading_days:
    regime = day_regimes.get(day, 'NORMAL')
    if regime not in TRADEABLE_REGIMES:
        eod_row = eod_data[eod_data['dt'] == day]
        if not eod_row.empty:
            prev_close = float(eod_row.iloc[0]['close'])
        continue

    day_data = data[data['date'] == day].copy()
    c15 = build_15min_spot(day_data)
    if len(c15) < 4:
        continue

    pcr   = calc_pcr(day_data)
    ctx   = compute_day_context(c15, prev_close, pcr)
    expiry = (day.weekday() == cfg.expiry_dow)
    day_ohlc = {'open': float(c15.iloc[0]['close']),
                'high': float(c15['high'].max()),
                'low':  float(c15['low'].min()),
                'close':float(c15.iloc[-1]['close'])}

    trades_today = defaultdict(int)

    for i in range(3, len(c15)):
        row  = c15.iloc[i]
        ts_v = row.get('ts_ist') if hasattr(row,'get') else getattr(row,'ts_ist',None)
        ts   = pd.Timestamp(ts_v) if ts_v is not None else pd.Timestamp('2000-01-01')
        hhmm = ts.hour * 100 + ts.minute
        if hhmm < 945 or hhmm > 1400:
            continue

        state = compute_intraday_state(c15.iloc[:i+1], pcr)

        for strat in active_strats:
            if strat.name not in idx_profiles:
                continue
            entry_start = ENTRY_START.get(strat.name, strat.entry_start)
            entry_cut   = ENTRY_CUTOFF.get(strat.name, strat.entry_end)
            if hhmm < entry_start or hhmm > entry_cut:
                continue
            if strat.name == 'BEAR_TREND_FOLLOWER' and regime != 'TRENDING_BEAR':
                continue
            if strat.name == 'BULL_TREND_FOLLOWER' and regime != 'TRENDING_BULL':
                continue

            dirs = ['CE','PE'] if strat.direction == 'BOTH' else [strat.direction]
            for direction in dirs:
                if direction == 'CE' and trades_today['CE'] >= cfg.max_ce_day:
                    continue
                if direction == 'PE' and trades_today['PE'] >= 1:
                    continue

                profile = idx_profiles[strat.name]
                armed, conf, reason = match_profile(profile, ctx, state, direction)
                if not armed:
                    continue

                opt_b = day_data[
                    (day_data['option_type_flag'] == direction) &
                    (day_data['strike'] == strat.strike) &
                    (day_data['hhmm'] == hhmm)
                ]
                if len(opt_b) == 0:
                    continue

                prem = float(opt_b.iloc[0]['close'])
                min_req = strat.min_premium * cfg.premium_scale
                max_req = strat.max_premium * cfg.premium_scale
                if prem < min_req or prem > max_req:
                    continue

                norm_prem = prem / cfg.premium_scale
                try:
                    ok = signal_check(strat, direction, c15.iloc[:i+1], day_ohlc, pcr, hhmm, expiry, norm_prem)
                except Exception as e:
                    ok = True
                    continue

                detail = {
                    'day': day, 'hhmm': hhmm, 'strat': strat.name, 'dir': direction,
                    'prem': prem, 'norm_prem': norm_prem,
                    'pcr': pcr, 'rsi': state.rsi, 'regime': regime, 'result': ok
                }
                if ok:
                    signal_pass_details.append(detail)
                    trades_today[direction] += 1
                else:
                    signal_fail_details.append(detail)

    eod_row = eod_data[eod_data['dt'] == day]
    if not eod_row.empty:
        prev_close = float(eod_row.iloc[0]['close'])

print(f'signal_check PASS: {len(signal_pass_details)}')
print(f'signal_check FAIL: {len(signal_fail_details)}')

if signal_fail_details:
    fail_df = pd.DataFrame(signal_fail_details)
    print('\nFail by strategy:')
    print(fail_df.groupby(['strat','dir']).size().to_string())
    print('\nFail norm_prem stats:')
    print(fail_df.groupby(['strat','dir'])['norm_prem'].describe().to_string())
    print('\nFail pcr stats:')
    print(fail_df['pcr'].describe())
    print('\nFail RSI stats:')
    print(fail_df['rsi'].describe())
    print('\nSample fail records:')
    print(fail_df[['day','hhmm','strat','dir','prem','norm_prem','pcr','rsi','regime']].head(20).to_string())

# Now check: what does signal_check actually look at internally?
print('\n\n=== INSPECTING signal_check SOURCE ===')
import inspect
src = inspect.getsource(signal_check)
print(src[:3000])
