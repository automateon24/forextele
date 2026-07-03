#!/usr/bin/env python3
"""
SIGNAL AUDIT — answer: do ALL 21 strategies fire on all 110 tradeable days?
For every day, for every strategy, count:
  - Did signal fire?
  - If yes, what was the trade result?
  - What is blocking it (no data, wrong regime, no signal, premium OOB)?
"""
import sys
sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd
import numpy as np
from collections import defaultdict

from BACKTEST_V3_TUNED import (
    load_option_data, load_eod_data,
    make_strategies, signal_check, build_15min_spot,
    calc_pcr, is_expiry_day, execute_trade
)
from regime_detector import label_days, STRATEGY_REGIME_MATRIX

opt_data = load_option_data()
eod_data = load_eod_data()
strategies = make_strategies()
day_regimes = label_days(opt_data)
trading_days = sorted(opt_data['date'].unique())

TRADEABLE = {'TRENDING_BULL', 'TRENDING_BEAR', 'NORMAL'}

print(f"\nTotal days: {len(trading_days)}")
print(f"Tradeable regimes (non HIGH_VOL/RANGE): {sum(1 for d in trading_days if day_regimes.get(d,'NORMAL') in TRADEABLE)}")
print(f"Strategies in V3: {len(strategies)}")

# Per strategy: count fire days, no-data days, no-signal days, regime-blocked days
strat_stats = defaultdict(lambda: {
    'fire': 0, 'no_data': 0, 'no_signal': 0, 'regime_block': 0,
    'prem_oob': 0, 'total_days': 0, 'pnl': 0.0, 'wins': 0, 'trades': 0
})

no_signal_days = set()

for day in trading_days:
    regime = day_regimes.get(day, 'NORMAL')
    day_data = opt_data[opt_data['date'] == day].copy()
    c15 = build_15min_spot(day_data)
    if len(c15) < 3:
        continue
    pcr = calc_pcr(day_data)
    expiry = is_expiry_day(day)
    eod_row = eod_data[eod_data['dt'] == day]
    if not eod_row.empty:
        r = eod_row.iloc[0]
        day_ohlc = {'open': r['open'], 'high': r['high'], 'low': r['low']}
    else:
        day_ohlc = {'open': float(day_data['spot'].iloc[0]),
                    'high': float(day_data['spot'].max()),
                    'low':  float(day_data['spot'].min())}

    day_fired_any = False

    for strat in strategies:
        strat_stats[strat.name]['total_days'] += 1

        # Regime block check
        strat_flags = STRATEGY_REGIME_MATRIX.get(strat.name, {})
        if strat_flags and not strat_flags.get(regime, True):
            strat_stats[strat.name]['regime_block'] += 1
            continue

        dirs = ['CE', 'PE'] if strat.direction == 'BOTH' else [strat.direction]

        for direction in dirs:
            opt_type = direction
            # Check option data available
            opt_bars = day_data[
                (day_data['option_type_flag'] == opt_type) &
                (day_data['strike'] == strat.strike)
            ]
            if len(opt_bars) == 0:
                strat_stats[strat.name]['no_data'] += 1
                continue

            # Walk 15min bars in entry window
            fired_today = False
            for i, row in c15.iterrows():
                ts = row['ts_ist'] if hasattr(row['ts_ist'], 'hour') else pd.Timestamp(row['ts_ist'])
                hhmm = ts.hour * 100 + ts.minute
                if hhmm < strat.entry_start or hhmm > strat.entry_end:
                    continue

                candles = c15.iloc[:i+1]
                opt_b = day_data[
                    (day_data['option_type_flag'] == opt_type) &
                    (day_data['strike'] == strat.strike) &
                    (day_data['hhmm'] == hhmm)
                ]
                prem = float(opt_b['close'].iloc[-1]) if len(opt_b) > 0 else 999.0

                if prem < strat.min_premium or prem > strat.max_premium:
                    continue  # premium OOB

                if signal_check(strat, direction, candles, day_ohlc, pcr, hhmm, expiry, prem):
                    strat_stats[strat.name]['fire'] += 1
                    fired_today = True
                    day_fired_any = True

                    # Execute trade
                    strike_bars = day_data[
                        (day_data['option_type_flag'] == opt_type) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] >= hhmm)
                    ].reset_index(drop=True)
                    spot_bars = None
                    if 'spot' in day_data.columns:
                        spot_bars = day_data[day_data['hhmm'] >= hhmm][['hhmm','spot']].rename(
                            columns={'spot':'close'}).drop_duplicates('hhmm').reset_index(drop=True)

                    trade = execute_trade(0, strike_bars, strat, direction,
                                         day_ohlc=day_ohlc if strat.name == 'ULTIMATE_DAY_HIGH_LOW' else None,
                                         spot_bars=spot_bars)
                    if trade:
                        strat_stats[strat.name]['trades'] += 1
                        strat_stats[strat.name]['pnl'] += trade.pnl_rs
                        if trade.won:
                            strat_stats[strat.name]['wins'] += 1
                    break  # one trade per strategy per direction per day

            if not fired_today:
                strat_stats[strat.name]['no_signal'] += 1

    if not day_fired_any:
        no_signal_days.add(day)

print(f"\nDays where NO strategy fired at all: {len(no_signal_days)}")
print(f"Days where at least 1 strategy fired: {len(trading_days) - len(no_signal_days)}")

# Print full strategy signal audit
print(f"\n{'Strategy':<30} {'Days':>5} {'Fire':>5} {'NoSig':>6} {'RegBlk':>7} {'NoData':>7} {'Trades':>7} {'WR%':>5} {'PnL':>10}")
print('-'*95)

total_pnl = 0
total_trades = 0
for strat in strategies:
    s = strat_stats[strat.name]
    wr = 100*s['wins']//max(s['trades'],1) if s['trades']>0 else 0
    print(f"{strat.name:<30} {s['total_days']:>5} {s['fire']:>5} {s['no_signal']:>6} "
          f"{s['regime_block']:>7} {s['no_data']:>7} {s['trades']:>7} {wr:>4}% {s['pnl']:>+10,.0f}")
    total_pnl   += s['pnl']
    total_trades += s['trades']

print('-'*95)
print(f"{'ALL STRATEGIES COMBINED':<30} {'':>5} {'':>5} {'':>6} {'':>7} {'':>7} {total_trades:>7} {'':>5} {total_pnl:>+10,.0f}")

# Diagnose why no_signal days have no signal
print(f"\n\nSample days with zero signals — why?")
sample = sorted(no_signal_days)[:10]
for day in sample:
    regime = day_regimes.get(day, 'NORMAL')
    dd = opt_data[opt_data['date'] == day]
    c15 = build_15min_spot(dd)
    spot_range = float(dd['spot'].max()) - float(dd['spot'].min()) if 'spot' in dd.columns else 0
    print(f"  {day}  regime={regime:<18} bars={len(c15):>3}  spot_range={spot_range:.0f}pts  rows={len(dd)}")
