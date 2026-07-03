"""
Deep diagnostic: why does BANKNIFTY only get 14 trades over 155 days?
Traces every armed signal and why it fails at each gate.
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

cfg         = INDEX_CONFIGS[IDX]
idx_profiles = INDEX_PROFILES[IDX]
active_strats = [s for s in make_strategies() if s.name in ACTIVE_STRATEGIES]
day_regimes   = label_days(data)
trading_days  = sorted(data['date'].unique())

print(f'{IDX}: {len(data)} rows, {len(trading_days)} days')
print(f'Profiles available: {list(idx_profiles.keys())}')
print()

# ── Counters ─────────────────────────────────────────────────────────────────
gate_counts = {
    'regime_skip': 0,
    'no_c15':      0,
    'hhmm_filter': 0,
    'profile_fail':0,
    'opt_b_miss':  0,      # opt_b lookup = 0 rows
    'premium_filter': 0,
    'signal_fail': 0,
    'exec_bars_miss': 0,
    'fired': 0,
}
profile_fail_reasons = {}
premium_details = []

prev_close = 0.0
ce_spot = data[data['option_type_flag']=='CE'][['date','spot']].copy()
eod_data = ce_spot.groupby('date').agg(
    open=('spot','first'), high=('spot','max'),
    low=('spot','min'),  close=('spot','last')
).reset_index().rename(columns={'date':'dt'})

from collections import defaultdict

for day in trading_days:
    regime = day_regimes.get(day, 'NORMAL')
    if regime not in TRADEABLE_REGIMES:
        gate_counts['regime_skip'] += 1
        eod_row = eod_data[eod_data['dt'] == day]
        if not eod_row.empty:
            prev_close = float(eod_row.iloc[0]['close'])
        continue

    day_data = data[data['date'] == day].copy()
    c15 = build_15min_spot(day_data)
    if len(c15) < 4:
        gate_counts['no_c15'] += 1
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
            gate_counts['hhmm_filter'] += 1
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
                    gate_counts['profile_fail'] += 1
                    key = f'{strat.name}/{direction}: {reason}'
                    profile_fail_reasons[key] = profile_fail_reasons.get(key, 0) + 1
                    continue

                # opt_b lookup
                opt_b = day_data[
                    (day_data['option_type_flag'] == direction) &
                    (day_data['strike'] == strat.strike) &
                    (day_data['hhmm'] == hhmm)
                ]
                if len(opt_b) == 0:
                    gate_counts['opt_b_miss'] += 1
                    continue

                prem = float(opt_b.iloc[0]['close'])
                norm_prem = prem / cfg.premium_scale

                # premium filter
                if prem < strat.min_premium * cfg.premium_scale or prem > strat.max_premium * cfg.premium_scale:
                    gate_counts['premium_filter'] += 1
                    premium_details.append({
                        'day': day, 'strat': strat.name, 'dir': direction,
                        'prem': prem, 'min_req': strat.min_premium * cfg.premium_scale,
                        'max_req': strat.max_premium * cfg.premium_scale
                    })
                    continue

                # signal_check
                try:
                    ok = signal_check(strat, direction, c15.iloc[:i+1], day_ohlc, pcr, hhmm, expiry, norm_prem)
                except Exception as e:
                    ok = True
                if not ok:
                    gate_counts['signal_fail'] += 1
                    continue

                exec_bars = day_data[
                    (day_data['option_type_flag'] == direction) &
                    (day_data['strike'] == strat.strike) &
                    (day_data['hhmm'] > hhmm)
                ].reset_index(drop=True)
                if len(exec_bars) < 2:
                    gate_counts['exec_bars_miss'] += 1
                    continue

                gate_counts['fired'] += 1
                trades_today[direction] += 1

    eod_row = eod_data[eod_data['dt'] == day]
    if not eod_row.empty:
        prev_close = float(eod_row.iloc[0]['close'])

# ── Report ───────────────────────────────────────────────────────────────────
print('=== GATE BREAKDOWN (BANKNIFTY, all 155 days) ===')
for k, v in gate_counts.items():
    print(f'  {k:25s}: {v:6d}')

print()
print('=== TOP 20 PROFILE FAIL REASONS ===')
top_fails = sorted(profile_fail_reasons.items(), key=lambda x: -x[1])[:20]
for reason, cnt in top_fails:
    print(f'  {cnt:6d}  {reason}')

print()
print('=== PREMIUM FILTER DETAILS ===')
if premium_details:
    pdf = pd.DataFrame(premium_details)
    print(f'Total blocked by premium: {len(pdf)}')
    print(f'prem range: {pdf.prem.min():.0f} - {pdf.prem.max():.0f}')
    print(f'min_req range: {pdf.min_req.min():.0f} - {pdf.min_req.max():.0f}')
    print(f'max_req range: {pdf.max_req.min():.0f} - {pdf.max_req.max():.0f}')
    print()
    print('By strategy:')
    print(pdf.groupby(['strat','dir'])['prem'].agg(['count','min','median','max']).to_string())
else:
    print('None blocked by premium filter.')
