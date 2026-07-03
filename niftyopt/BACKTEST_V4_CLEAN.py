#!/usr/bin/env python3
"""
BACKTEST V4 CLEAN — Fixed Architecture
=======================================

KEY FIXES vs V3:
1. ONE best strategy per day (not 21 firing simultaneously)
2. Regime detector picks which strategy family to use
3. Max 3 trades per day total (simulate real trading discipline)
4. Proper capital: 1 lot = 75 units, capital tracked correctly
5. Confidence scoring: only take trade if signal score >= threshold
6. No duplicate signals — strategies are mutually exclusive per day slot

Target: 10% daily on ₹1,00,000 capital = ₹10,000/day
"""

from __future__ import annotations
import sys, os
sys.path.insert(0, 'c:/cursor/options/niftyopt')

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import date, timedelta
from collections import defaultdict

from BACKTEST_V3_TUNED import (
    load_option_data, load_eod_data,
    calc_rsi, calc_vwap, build_15min_spot, calc_pcr, is_expiry_day
)
from regime_detector import RegimeDetector, label_days, STRATEGY_REGIME_MATRIX

# ─────────────────────────────────────────────────────────────────────────────
# CAPITAL CONFIG
# ─────────────────────────────────────────────────────────────────────────────
LOT_SIZE        = 75          # NIFTY lot size
CAPITAL         = 100_000     # ₹1 lakh per "strategy slot"
BROKERAGE       = 40          # ₹20 buy + ₹20 sell (realistic)
MAX_TRADES_DAY  = 3           # max trades allowed per day
MIN_CONFIDENCE  = 0.68        # minimum signal confidence to trade (0-1)
DAILY_LOSS_LIMIT = -5000      # stop trading day if cumulative loss exceeds this

# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL CONFIDENCE SCORER
# Scores 0.0 to 1.0 — higher = more confident entry
# ─────────────────────────────────────────────────────────────────────────────
def score_signal(candles: pd.DataFrame, direction: str, regime: str,
                 pcr: float, hhmm: int, day_ohlc: dict) -> float:
    """
    Returns confidence score 0.0-1.0 for a potential entry.
    Combines: RSI extremity, trend alignment, time of day, regime fit,
              PCR alignment, candle body strength.
    """
    if len(candles) < 3:
        return 0.0

    score = 0.0
    c = candles.iloc[-1]
    spot = c['close']

    # --- RSI score (0.0-0.25) ---
    closes = candles['close'].values
    rsi = calc_rsi(pd.Series(closes))
    if direction == 'CE':
        if rsi < 35:   score += 0.25   # very oversold → strong CE signal
        elif rsi < 45: score += 0.15
        elif rsi < 55: score += 0.05
    else:  # PE
        if rsi > 65:   score += 0.25   # very overbought → strong PE signal
        elif rsi > 55: score += 0.15
        elif rsi > 45: score += 0.05

    # --- Regime alignment (0.0-0.20) ---
    regime_ce_regimes = ['TRENDING_BULL', 'RANGE_BOUND', 'NORMAL']
    regime_pe_regimes = ['TRENDING_BEAR', 'RANGE_BOUND', 'NORMAL']
    if direction == 'CE' and regime in regime_ce_regimes:
        score += 0.20
    elif direction == 'PE' and regime in regime_pe_regimes:
        score += 0.20
    elif regime == 'HIGH_VOLATILITY':
        score += 0.05  # low confidence in high-vol

    # --- Time of day (0.0-0.20) ---
    # Best window: 10:30-11:30 (morning trend) and 13:00-14:00 (afternoon)
    if 1030 <= hhmm <= 1130:
        score += 0.20
    elif 1300 <= hhmm <= 1400:
        score += 0.18
    elif 1130 <= hhmm <= 1300:
        score += 0.10
    elif 1000 <= hhmm <= 1030:
        score += 0.08
    else:
        score += 0.02

    # --- PCR alignment (0.0-0.15) ---
    if direction == 'CE' and pcr < 0.90:     score += 0.15  # low PCR = bearish OI = bullish spot
    elif direction == 'CE' and pcr < 1.10:   score += 0.08
    elif direction == 'PE' and pcr > 1.20:   score += 0.15  # high PCR = bearish
    elif direction == 'PE' and pcr > 1.00:   score += 0.08

    # --- Candle body strength (0.0-0.10) ---
    if len(candles) >= 2:
        prev_c = candles.iloc[-2]
        body = abs(c['close'] - c['open'])
        prev_body = abs(prev_c['close'] - prev_c['open'])
        if body > prev_body * 1.5:
            score += 0.10  # accelerating momentum
        elif body > prev_body:
            score += 0.05

    # --- Day position filter (0.0-0.10) ---
    day_range = day_ohlc.get('high', spot) - day_ohlc.get('low', spot)
    if day_range > 0:
        pos = (spot - day_ohlc.get('low', spot)) / day_range
        if direction == 'CE' and pos < 0.35:   score += 0.10  # near day low = CE buy opportunity
        elif direction == 'PE' and pos > 0.65: score += 0.10  # near day high = PE sell opportunity
        else:                                  score += 0.03

    return min(score, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# REGIME → STRATEGY PRIORITY MAP
# Best strategy to use for each regime (ordered by historical performance)
# ─────────────────────────────────────────────────────────────────────────────
REGIME_STRATEGY_PRIORITY: Dict[str, List[str]] = {
    'TRENDING_BULL':   ['DAY_LOW_BULLISH', 'BREAKOUT', 'TREND_FOLLOWING', 'MAGIC_SQUARE'],
    'TRENDING_BEAR':   ['DAY_HIGH_BEARISH', 'BREAKOUT', 'TREND_FOLLOWING', 'SHORT_UNWIND'],
    'RANGE_BOUND':     ['ULTIMATE_DAY_HIGH_LOW', 'MEAN_REVERSION'],   # only 2 — strict
    'HIGH_VOLATILITY': ['ZERO_HERO', 'GAMMA_BLAST', 'OPTIONS_GREEKS'],
    'NORMAL':          ['TREND_FOLLOWING', 'MAGIC_SQUARE', 'OPTIONS_GREEKS'],
}

# Direction override per regime (force CE/PE based on regime, not just strategy)
REGIME_DIRECTION_OVERRIDE: Dict[str, str] = {
    'TRENDING_BULL': 'CE',    # only buy calls on bull days
    'TRENDING_BEAR': 'PE',    # only buy puts on bear days
    'RANGE_BOUND':   'BOTH',  # can go either direction
    'HIGH_VOLATILITY': 'BOTH',
    'NORMAL':        'BOTH',
}

# Directions to try for each strategy
STRATEGY_DIRECTION: Dict[str, str] = {
    'TREND_FOLLOWING':       'BOTH',
    'DAY_LOW_BULLISH':       'CE',
    'DAY_HIGH_BEARISH':      'PE',
    'BREAKOUT':              'BOTH',
    'MAGIC_SQUARE':          'BOTH',
    'ULTIMATE_DAY_HIGH_LOW': 'BOTH',
    'MEAN_REVERSION':        'BOTH',
    'SCALPING':              'CE',
    'SHORT_UNWIND':          'CE',
    'LONG_UNWIND':           'PE',
    'ZERO_HERO':             'PE',
    'GAMMA_BLAST':           'BOTH',
    'OPTIONS_GREEKS':        'BOTH',
    'AI_ENHANCED':           'BOTH',
}

# SL/Target per strategy (tuned from V3 analysis)
STRATEGY_PARAMS: Dict[str, dict] = {
    'TREND_FOLLOWING':       {'sl': 0.15, 'tgt': 0.30, 'min_prem': 50,  'max_prem': 400},
    'DAY_LOW_BULLISH':       {'sl': 0.15, 'tgt': 0.25, 'min_prem': 50,  'max_prem': 350},
    'DAY_HIGH_BEARISH':      {'sl': 0.15, 'tgt': 0.25, 'min_prem': 50,  'max_prem': 350},
    'BREAKOUT':              {'sl': 0.15, 'tgt': 0.30, 'min_prem': 40,  'max_prem': 350},
    'MAGIC_SQUARE':          {'sl': 0.15, 'tgt': 0.25, 'min_prem': 50,  'max_prem': 350},
    'ULTIMATE_DAY_HIGH_LOW': {'sl': 0.10, 'tgt': 0.35, 'min_prem': 50,  'max_prem': 350},
    'MEAN_REVERSION':        {'sl': 0.12, 'tgt': 0.20, 'min_prem': 40,  'max_prem': 300},
    'SCALPING':              {'sl': 0.10, 'tgt': 0.20, 'min_prem': 30,  'max_prem': 200},
    'SHORT_UNWIND':          {'sl': 0.12, 'tgt': 0.20, 'min_prem': 50,  'max_prem': 300},
    'LONG_UNWIND':           {'sl': 0.15, 'tgt': 0.25, 'min_prem': 50,  'max_prem': 300},
    'ZERO_HERO':             {'sl': 0.30, 'tgt': 2.00, 'min_prem': 5,   'max_prem': 50},
    'GAMMA_BLAST':           {'sl': 0.20, 'tgt': 0.80, 'min_prem': 10,  'max_prem': 100},
    'OPTIONS_GREEKS':        {'sl': 0.15, 'tgt': 0.30, 'min_prem': 50,  'max_prem': 400},
    'AI_ENHANCED':           {'sl': 0.15, 'tgt': 0.30, 'min_prem': 50,  'max_prem': 400},
}


# ─────────────────────────────────────────────────────────────────────────────
# TRADE RECORD
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Trade:
    date:        object
    strategy:    str
    direction:   str
    regime:      str
    confidence:  float
    entry_time:  object
    entry_price: float
    exit_price:  float = 0.0
    exit_time:   object = None
    exit_reason: str   = ''
    pnl_pts:     float = 0.0
    pnl_rs:      float = 0.0
    won:         bool  = False


# ─────────────────────────────────────────────────────────────────────────────
# TRADE EXECUTOR
# ─────────────────────────────────────────────────────────────────────────────
def execute_v4(entry_bar: pd.Series, remaining_bars: pd.DataFrame,
               direction: str, params: dict,
               spot_bars: pd.DataFrame = None) -> Tuple[float, str, object]:
    """
    Executes a trade from entry bar through remaining bars.
    Returns (exit_price, exit_reason, exit_time).
    """
    entry_price  = float(entry_bar['open'])
    sl_price     = entry_price * (1 - params['sl'])
    target_price = entry_price * (1 + params['tgt'])
    tsl_high     = entry_price
    tsl_activated = False
    TSL_ACTIVATION = 0.08   # unlock TSL once 8% in profit
    TSL_TRAIL_PCT  = 0.04   # trail 4% below peak

    exit_price  = None
    exit_reason = 'EOD'
    exit_time   = None

    for _, bar in remaining_bars.iterrows():
        hi = float(bar.get('high', bar['close']))
        lo = float(bar.get('low',  bar['close']))
        tsl_high = max(tsl_high, hi)

        # Hard SL
        if lo <= sl_price:
            exit_price  = sl_price
            exit_reason = 'SL'
            exit_time   = bar['ts_ist']
            break

        # Target
        if hi >= target_price:
            exit_price  = target_price
            exit_reason = 'TARGET'
            exit_time   = bar['ts_ist']
            break

        # TSL: activate once TSL_ACTIVATION profit, trail TSL_TRAIL_PCT below peak
        if tsl_high >= entry_price * (1 + TSL_ACTIVATION):
            tsl_activated = True
        if tsl_activated:
            tsl_floor = tsl_high * (1 - TSL_TRAIL_PCT)
            if lo <= tsl_floor and tsl_floor > sl_price:
                exit_price  = max(tsl_floor, sl_price)
                exit_reason = 'TSL'
                exit_time   = bar['ts_ist']
                break

    if exit_price is None:
        last_bar   = remaining_bars.iloc[-1] if len(remaining_bars) > 0 else entry_bar
        exit_price = float(last_bar['close'])
        exit_time  = last_bar['ts_ist']
        exit_reason= 'EOD'

    exit_price = max(exit_price, 0.05)
    return exit_price, exit_reason, exit_time


# ─────────────────────────────────────────────────────────────────────────────
# MAIN BACKTEST
# ─────────────────────────────────────────────────────────────────────────────
def run_backtest_v4(opt_data: pd.DataFrame, eod_data: pd.DataFrame) -> List[Trade]:
    trading_days = sorted(opt_data['date'].unique())
    all_trades: List[Trade] = []

    # Pre-label regimes
    day_regimes = label_days(opt_data)

    print(f"\n{'='*65}")
    print(f"BACKTEST V4 CLEAN — {len(trading_days)} days")
    print(f"Capital: ₹{CAPITAL:,} | Max {MAX_TRADES_DAY} trades/day | Min confidence: {MIN_CONFIDENCE}")
    print(f"{'='*65}\n")
    print("Regime distribution:")
    print(day_regimes.value_counts().to_string())
    print()

    for day in trading_days:
        day_data = opt_data[opt_data['date'] == day].copy()
        expiry   = is_expiry_day(day)
        regime   = day_regimes.get(day, 'NORMAL')

        # Get day OHLC
        eod_row = eod_data[eod_data['dt'] == day]
        if eod_row.empty:
            day_open = float(day_data['spot'].iloc[0])
            day_high = float(day_data['spot'].max())
            day_low  = float(day_data['spot'].min())
        else:
            r = eod_row.iloc[0]
            day_open, day_high, day_low = r['open'], r['high'], r['low']
        day_ohlc = {'open': day_open, 'high': day_high, 'low': day_low}

        c15 = build_15min_spot(day_data)
        if len(c15) < 3:
            continue
        pcr = calc_pcr(day_data)

        # Get strategy priority list for today's regime
        priority = REGIME_STRATEGY_PRIORITY.get(regime, REGIME_STRATEGY_PRIORITY['NORMAL'])

        # Skip GAMMA_BLAST on non-expiry
        if not expiry and 'GAMMA_BLAST' in priority:
            priority = [s for s in priority if s != 'GAMMA_BLAST']

        trades_today  = 0
        cumulative_pnl = 0.0
        used_slots: set = set()  # (direction, hhmm) already traded

        for i, row in c15.iterrows():
            if trades_today >= MAX_TRADES_DAY:
                break
            if cumulative_pnl <= DAILY_LOSS_LIMIT:
                break  # daily loss limit hit

            ts = row['ts_ist'] if hasattr(row['ts_ist'], 'hour') else pd.Timestamp(row['ts_ist'])
            hhmm = ts.hour * 100 + ts.minute

            # Only trade between 9:30 and 14:30
            if hhmm < 930 or hhmm > 1430:
                continue

            candles_so_far = c15.iloc[:i+1]

            # Try each strategy in priority order until one fires with enough confidence
            for strat_name in priority:
                if strat_name not in STRATEGY_PARAMS:
                    continue
                params  = STRATEGY_PARAMS[strat_name]
                dirs    = STRATEGY_DIRECTION.get(strat_name, 'BOTH')
                # Regime direction override: on TRENDING days only trade with the trend
                regime_dir_override = REGIME_DIRECTION_OVERRIDE.get(regime, 'BOTH')
                if regime_dir_override != 'BOTH':
                    directions = [regime_dir_override]
                else:
                    directions = ['CE', 'PE'] if dirs == 'BOTH' else [dirs]

                for direction in directions:
                    slot = (direction, hhmm // 100)  # one trade per direction per hour
                    if slot in used_slots:
                        continue

                    # Get option bars
                    opt_type = direction
                    opt_bars = day_data[
                        (day_data['option_type_flag'] == opt_type) &
                        (day_data['strike'] == 'ATM') &
                        (day_data['hhmm'] == hhmm)
                    ]
                    if len(opt_bars) == 0:
                        continue
                    opt_premium = float(opt_bars['close'].iloc[-1])

                    # Premium filter
                    if opt_premium < params['min_prem'] or opt_premium > params['max_prem']:
                        continue

                    # Score the signal
                    conf = score_signal(candles_so_far, direction, regime, pcr, hhmm, day_ohlc)
                    if conf < MIN_CONFIDENCE:
                        continue

                    # Get execution bars
                    exec_bars = day_data[
                        (day_data['option_type_flag'] == opt_type) &
                        (day_data['strike'] == 'ATM') &
                        (day_data['hhmm'] > hhmm)
                    ].reset_index(drop=True)

                    if len(exec_bars) < 2:
                        continue

                    # Entry at next bar open
                    entry_bar   = exec_bars.iloc[0]
                    entry_price = float(entry_bar['open'])
                    if entry_price < params['min_prem'] or entry_price > params['max_prem']:
                        continue

                    remaining   = exec_bars.iloc[1:].copy()
                    remaining['ts_ist'] = remaining['ts_ist']

                    exit_price, exit_reason, exit_time = execute_v4(
                        entry_bar, remaining, direction, params)

                    pnl_pts = exit_price - entry_price
                    pnl_rs  = round(pnl_pts * LOT_SIZE - BROKERAGE, 2)

                    trade = Trade(
                        date        = day,
                        strategy    = strat_name,
                        direction   = direction,
                        regime      = regime,
                        confidence  = round(conf, 3),
                        entry_time  = entry_bar['ts_ist'],
                        entry_price = entry_price,
                        exit_price  = exit_price,
                        exit_time   = exit_time,
                        exit_reason = exit_reason,
                        pnl_pts     = round(pnl_pts, 2),
                        pnl_rs      = pnl_rs,
                        won         = pnl_rs > 0,
                    )
                    all_trades.append(trade)
                    used_slots.add(slot)
                    trades_today  += 1
                    cumulative_pnl += pnl_rs
                    break  # one strategy fired for this direction/time slot

                if trades_today >= MAX_TRADES_DAY:
                    break

    return all_trades


# ─────────────────────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────────────────────
def report(trades: List[Trade], opt_data: pd.DataFrame):
    DAYS = opt_data['date'].nunique()
    date_min = opt_data['date'].min()
    date_max = opt_data['date'].max()

    if not trades:
        print("No trades generated.")
        return

    total    = sum(t.pnl_rs for t in trades)
    daily    = total / DAYS
    monthly  = daily * 22
    day_pct  = daily / CAPITAL * 100
    wins     = sum(1 for t in trades if t.won)
    win_rate = 100 * wins / len(trades)

    print(f"\n{'='*70}")
    print(f"BACKTEST V4 RESULTS  |  {DAYS} days  ({date_min} → {date_max})")
    print(f"{'='*70}")
    print(f"  Total trades   : {len(trades)}")
    print(f"  Win rate       : {win_rate:.1f}%")
    print(f"  Total PnL      : ₹{total:+,.0f}")
    print(f"  Daily avg PnL  : ₹{daily:+,.0f}")
    print(f"  Daily avg %    : {day_pct:+.2f}%  (target: 10%)")
    print(f"  Monthly est.   : ₹{monthly:+,.0f}  ({monthly/CAPITAL*100:.1f}% on ₹{CAPITAL:,})")

    # Per-year
    t25 = [t for t in trades if str(t.date).startswith('2025')]
    t26 = [t for t in trades if str(t.date).startswith('2026')]
    d25 = len(set(t.date for t in t25)) or 1
    d26 = len(set(t.date for t in t26)) or 1
    p25 = sum(t.pnl_rs for t in t25)
    p26 = sum(t.pnl_rs for t in t26)
    print(f"\n  2025: ₹{p25:+,.0f}  ({d25} days, {len(t25)} trades, avg ₹{p25/d25:+.0f}/day, {p25/d25/CAPITAL*100:.1f}%/day)")
    print(f"  2026: ₹{p26:+,.0f}  ({d26} days, {len(t26)} trades, avg ₹{p26/d26:+.0f}/day, {p26/d26/CAPITAL*100:.1f}%/day)")

    # Per-strategy
    print(f"\n{'='*70}")
    print(f"{'Strategy':<28} {'N':>4} {'Win%':>6} {'Total':>9} {'Avg/Day':>8} {'Day%':>7}")
    print(f"{'-'*70}")
    by_strat = defaultdict(list)
    for t in trades:
        by_strat[t.strategy].append(t)
    for name, ts in sorted(by_strat.items(), key=lambda x: sum(t.pnl_rs for t in x[1]), reverse=True):
        pnl = sum(t.pnl_rs for t in ts)
        wr  = 100 * sum(1 for t in ts if t.won) / len(ts)
        avd = pnl / DAYS
        pct = avd / CAPITAL * 100
        print(f"  {name:<26} {len(ts):>4} {wr:>5.0f}% {pnl:>+9,.0f} {avd:>+8,.0f} {pct:>+6.2f}%")

    # Per-regime
    print(f"\n{'='*70}")
    print(f"{'Regime':<22} {'Trades':>6} {'Win%':>6} {'Total':>9} {'Per Trade':>10}")
    print(f"{'-'*70}")
    by_regime = defaultdict(list)
    for t in trades:
        by_regime[t.regime].append(t)
    for reg, ts in sorted(by_regime.items(), key=lambda x: sum(t.pnl_rs for t in x[1]), reverse=True):
        pnl = sum(t.pnl_rs for t in ts)
        wr  = 100 * sum(1 for t in ts if t.won) / len(ts)
        pt  = pnl / len(ts)
        print(f"  {reg:<20} {len(ts):>6} {wr:>5.0f}% {pnl:>+9,.0f} {pt:>+10,.0f}")

    # Daily distribution
    daily_pnl = defaultdict(float)
    for t in trades:
        daily_pnl[t.date] += t.pnl_rs
    daily_vals = list(daily_pnl.values())
    green = sum(1 for v in daily_vals if v > 0)
    target_days = sum(1 for v in daily_vals if v >= CAPITAL * 0.10)
    print(f"\n  Green days     : {green}/{len(daily_vals)} ({100*green/max(len(daily_vals),1):.0f}%)")
    print(f"  10%+ days      : {target_days}/{len(daily_vals)} ({100*target_days/max(len(daily_vals),1):.0f}%)")
    print(f"  Best day       : ₹{max(daily_vals):+,.0f}")
    print(f"  Worst day      : ₹{min(daily_vals):+,.0f}")
    print(f"  Avg confidence : {sum(t.confidence for t in trades)/len(trades):.3f}")

    # Max drawdown
    cum = pd.Series(daily_vals).cumsum()
    dd  = (cum - cum.cummax()).min()
    print(f"  Max drawdown   : ₹{dd:+,.0f}")
    print(f"{'='*70}")

    # Top 10 best days
    top10 = sorted(daily_pnl.items(), key=lambda x: x[1], reverse=True)[:10]
    print(f"\nTop 10 days:")
    for d, v in top10:
        day_trades = [t for t in trades if t.date == d]
        strats = ', '.join(set(t.strategy for t in day_trades))
        print(f"  {d}  ₹{v:+,.0f}  ({len(day_trades)} trades: {strats})")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Loading data...")
    opt_data = load_option_data()
    eod_data = load_eod_data()

    trades = run_backtest_v4(opt_data, eod_data)
    report(trades, opt_data)
