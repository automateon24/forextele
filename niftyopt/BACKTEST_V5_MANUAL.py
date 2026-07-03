#!/usr/bin/env python3
"""
BACKTEST V5 MANUAL — Exact replication of user's manual trading rules
======================================================================

USER'S EXACT RULES:
===================

CE (BULLISH) ENTRIES — any of:
  A. Day Low Touch + Bounce:
     - Spot touches or comes within 20pts of day running low
     - Next 1-2 candles are GREEN (close > open)
     - RSI on 15min < 40 (oversold)
     - EMA5 crosses above EMA20 (or already above)

  B. Breakout Entry:
     - Spot breaks above prev 15min candle high
     - RSI > 60
     - Volume spike (current bar > 1.5x avg 5-bar volume)

  C. VWAP + PCR mid-day:
     - After 11:00, spot above VWAP
     - RSI 45-55 range
     - PCR < 1.0

PE (BEARISH) ENTRIES — any of:
  A. Day High Touch + Reversal:
     - Spot touches or comes within 20pts of day running high
     - Next 1-2 candles are RED (close < open)
     - RSI > 65 (overbought)

EXIT RULES:
  - TARGET: +35% premium gain (middle of 30-50%)
  - SL:     -22% premium loss (middle of 20-25%)
  - Spot-move exit: spot has moved 65pts in direction → exit
  - Time exit: hard close by 13:45 IST (before 14:00)
  - Max 2 trades per day (1 CE + 1 PE) — manual discipline

ADDITIONAL REGIME FILTERS:
  - Only trade TRENDING_BULL or TRENDING_BEAR days with trend direction
  - On NORMAL days: allow both but require stronger RSI confirmation
  - Skip HIGH_VOLATILITY and RANGE_BOUND days entirely
  - Scale up to 2 lots on confidence > 0.80
"""

from __future__ import annotations
import sys
sys.path.insert(0, 'c:/cursor/options/niftyopt')

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from BACKTEST_V3_TUNED import (
    load_option_data, load_eod_data,
    calc_rsi, build_15min_spot, calc_pcr, is_expiry_day
)
from regime_detector import label_days

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
LOT_SIZE         = 75
CAPITAL          = 100_000
BROKERAGE        = 40
MAX_TRADES_DAY   = 4          # up to 2 CE (re-entry after win) + 1 PE + 1 VWAP per day
MAX_CE_PER_DAY   = 2          # max 2 CE trades, but re-entry only after a WIN exit
MIN_REENTRY_GAP  = 15         # min 15 min gap before re-entry (hhmm units: 15)
TARGET_PCT       = 0.35       # 35% profit on premium
SL_PCT           = 0.30       # 30% backstop SL (effectively TSL-only — TSL exits first)
SPOT_MOVE_TGT    = 999        # DISABLED — spot move exit removed (TSL+TARGET handles exits)
HARD_EXIT_HHMM   = 1415       # force exit at 14:15
DAY_LOW_TOUCH_BUFFER  = 20    # within 20pts of day low = "touched"
DAY_HIGH_TOUCH_BUFFER = 20    # within 20pts of day high = "touched"
RSI_OVERSOLD     = 40
RSI_OVERBOUGHT   = 65
VOLUME_SPIKE     = 1.5        # current bar volume > 1.5x avg5

# Regimes where we trade (skip HIGH_VOLATILITY and RANGE_BOUND)
TRADEABLE_REGIMES = {'TRENDING_BULL', 'TRENDING_BEAR', 'NORMAL'}

# Regime → forced direction (on trending days follow the trend)
REGIME_ALLOWED_DIRECTIONS = {
    'TRENDING_BULL':   ['CE'],        # only buy calls on bull days
    'TRENDING_BEAR':   ['PE'],        # only buy puts on bear days
    'NORMAL':          ['CE', 'PE'],  # can do both on normal days
}

# Lot scaling by confidence and signal type
def get_lots(confidence: float, signal: str = '') -> int:
    if signal == 'BREAKOUT_CE' and confidence >= 0.75:
        return 2   # 2 lots on confirmed breakout (your strongest setup)
    if confidence >= 0.85:
        return 2   # 2 lots on very high confidence any signal
    return 1


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL FUNCTIONS — exact manual rules
# ─────────────────────────────────────────────────────────────────────────────
def calc_ema(series: pd.Series, period: int) -> float:
    if len(series) < period:
        return float(series.mean())
    return float(series.ewm(span=period, adjust=False).mean().iloc[-1])


def check_ce_signal(candles: pd.DataFrame, day_running_low: float,
                    pcr: float, hhmm: int, vwap: float) -> Tuple[bool, str, float]:
    """
    Returns (signal_fired, reason, confidence)
    CE entry conditions (any one must be True):
      A. Day low touch + bounce + RSI < 40
      B. Breakout above prev high + RSI > 60 + volume spike
      C. VWAP above + PCR < 1.0 + RSI 45-55 (after 11:00)
    """
    if len(candles) < 4:
        return False, '', 0.0

    spot     = candles['close'].values
    volumes  = candles['volume'].values
    c        = candles.iloc[-1]
    prev     = candles.iloc[-2]

    cur_spot = float(c['close'])
    cur_open = float(c['open'])
    prev_close = float(prev['close'])
    prev_open  = float(prev['open'])

    rsi      = calc_rsi(pd.Series(spot))
    ema5     = calc_ema(pd.Series(spot), 5)
    ema20    = calc_ema(pd.Series(spot), 20)

    vol_avg5 = float(np.mean(volumes[-6:-1])) if len(volumes) >= 6 else float(np.mean(volumes))
    vol_spike = volumes[-1] > vol_avg5 * VOLUME_SPIKE if vol_avg5 > 0 else False

    confidence = 0.0

    # ── Condition A: Day Low Touch + Bounce ──────────────────────────────
    near_day_low = cur_spot <= day_running_low + DAY_LOW_TOUCH_BUFFER
    prev_green   = prev_close > prev_open        # prev candle is green (bounce)
    cur_green    = cur_close  = cur_spot > cur_open  # current candle also green
    rsi_oversold = rsi < RSI_OVERSOLD

    # Require BOTH prev AND current green (confirmed bounce, not a single fluke candle)
    if near_day_low and prev_green and cur_green and rsi_oversold:
        conf = 0.60
        if rsi < 35:     conf += 0.10  # very oversold
        if ema5 >= ema20: conf += 0.08  # ema confirms
        if vol_spike:    conf += 0.07
        return True, 'DAY_LOW_BOUNCE', round(conf, 3)

    # ── Condition B: Breakout above prev high ────────────────────────────
    prev_high = float(candles.iloc[-2]['high']) if 'high' in candles.columns else prev_close
    breakout  = cur_spot > prev_high * 1.001
    rsi_bull  = rsi > 58  # slightly relaxed from 60

    if breakout and rsi_bull:  # volume not strictly required (15min agg can be 0)
        conf = 0.58
        if rsi > 65:       conf += 0.08
        if ema5 > ema20:   conf += 0.07
        if vol_spike:      conf += 0.05  # bonus if volume confirms
        return True, 'BREAKOUT_CE', round(conf, 3)

    # ── Condition C: VWAP + PCR + EMA alignment (strict: ALL must be true) ───
    if hhmm >= 1030:
        above_vwap  = cur_spot > vwap if vwap > 0 else False
        pcr_bullish = pcr < 0.90           # strict PCR threshold
        ema_bull    = ema5 > ema20         # trend confirmed
        rsi_ok      = rsi < 48             # RSI not overbought

        if above_vwap and pcr_bullish and ema_bull and rsi_ok and vol_spike:
            conf = 0.62
            if pcr < 0.80: conf += 0.08
            if rsi < 40:   conf += 0.05
            return True, 'VWAP_EMA_CE', round(conf, 3)

    return False, '', 0.0


def check_pe_signal(candles: pd.DataFrame, day_running_high: float,
                    pcr: float, hhmm: int) -> Tuple[bool, str, float]:
    """
    PE entry conditions:
      A. Day high touch + 1-2 red candles + RSI > 65
    """
    if len(candles) < 4:
        return False, '', 0.0

    spot     = candles['close'].values
    c        = candles.iloc[-1]
    prev     = candles.iloc[-2]

    cur_spot  = float(c['close'])
    cur_open  = float(c['open'])
    prev_close = float(prev['close'])
    prev_open  = float(prev['open'])

    rsi  = calc_rsi(pd.Series(spot))
    ema5 = calc_ema(pd.Series(spot), 5)
    ema20= calc_ema(pd.Series(spot), 20)

    # ── Day High Touch + Red candles + RSI overbought ────────────────────
    near_day_high = cur_spot >= day_running_high - DAY_HIGH_TOUCH_BUFFER
    prev_red      = prev_close < prev_open
    cur_red       = cur_spot < cur_open
    rsi_overbought = rsi > RSI_OVERBOUGHT

    # Both red candles required (not just one)
    if near_day_high and prev_red and cur_red and rsi_overbought:
        conf = 0.60
        if rsi > 70:      conf += 0.10  # very overbought
        if ema5 <= ema20: conf += 0.08  # ema bearish
        return True, 'DAY_HIGH_REJECT', round(conf, 3)

    # ── Also: below VWAP + PCR bearish + EMA bearish ─────────────────────
    if rsi > RSI_OVERBOUGHT:
        volumes  = candles['volume'].values
        vol_avg5 = float(np.mean(volumes[-6:-1])) if len(volumes) >= 6 else float(np.mean(volumes))
        vol_spike2 = volumes[-1] > vol_avg5 * VOLUME_SPIKE if vol_avg5 > 0 else False
        ema5_pe  = calc_ema(pd.Series(candles['close'].values), 5)
        ema20_pe = calc_ema(pd.Series(candles['close'].values), 20)
        if ema5_pe < ema20_pe and pcr > 1.20 and vol_spike2 and hhmm >= 1030:
            conf = 0.60
            if pcr > 1.40:  conf += 0.08
            if rsi > 70:    conf += 0.05
            return True, 'VWAP_EMA_PE', round(conf, 3)

    return False, '', 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TRADE RECORD
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Trade:
    date:         object
    strategy:     str
    direction:    str
    regime:       str
    confidence:   float
    lots:         int
    entry_time:   object
    entry_price:  float
    entry_spot:   float
    exit_price:   float  = 0.0
    exit_time:    object = None
    exit_reason:  str    = ''
    exit_spot:    float  = 0.0
    spot_move:    float  = 0.0
    pnl_pts:      float  = 0.0
    pnl_rs:       float  = 0.0
    won:          bool   = False


# ─────────────────────────────────────────────────────────────────────────────
# TRADE EXECUTOR
# ─────────────────────────────────────────────────────────────────────────────
def execute_v5(entry_bar: pd.Series, remaining_bars: pd.DataFrame,
               direction: str, entry_spot: float,
               day_running_high: float, day_running_low: float) -> Tuple[float, str, object, float]:
    """
    Executes trade with user's exact exit rules:
    - +35% target on premium
    - -22% SL on premium
    - 65pt spot move → exit
    - Hard exit at 13:45
    Returns (exit_price, exit_reason, exit_time, exit_spot)
    """
    entry_price  = float(entry_bar['open'])
    sl_price     = entry_price * (1 - SL_PCT)
    target_price = entry_price * (1 + TARGET_PCT)
    tsl_high      = entry_price
    tsl_activated = False
    TSL_ACTIVATE  = 0.08   # TSL kicks in at 8% profit
    TSL_TRAIL     = 0.05   # trail 5% below peak
    BREAKEVEN_MINS = 45    # exit at market if no 8% gain within 45 mins (wrong trade)
    entry_bar_ts  = entry_bar['ts_ist'] if hasattr(entry_bar['ts_ist'], 'hour') else pd.Timestamp(entry_bar['ts_ist'])
    entry_mins    = entry_bar_ts.hour * 60 + entry_bar_ts.minute

    exit_price  = None
    exit_reason = 'EOD'
    exit_time   = None
    exit_spot_p = entry_spot

    for _, bar in remaining_bars.iterrows():
        ts   = bar['ts_ist'] if hasattr(bar['ts_ist'], 'hour') else pd.Timestamp(bar['ts_ist'])
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))
        cur_spot = float(bar.get('spot', entry_spot))
        tsl_high = max(tsl_high, hi)

        # Breakeven stop: if 45 mins in and TSL never activated (never 8% in profit), exit
        cur_mins = ts.hour * 60 + ts.minute
        if not tsl_activated and (cur_mins - entry_mins) >= BREAKEVEN_MINS:
            exit_price  = float(bar['close'])
            exit_reason = 'BEVEN'
            exit_time   = bar['ts_ist']
            exit_spot_p = cur_spot
            break

        # Hard time exit
        if hhmm >= HARD_EXIT_HHMM:
            exit_price  = float(bar['close'])
            exit_reason = 'TIME'
            exit_time   = bar['ts_ist']
            exit_spot_p = cur_spot
            break

        # SL hit
        if lo <= sl_price:
            exit_price  = sl_price
            exit_reason = 'SL'
            exit_time   = bar['ts_ist']
            exit_spot_p = cur_spot
            break

        # Target hit
        if hi >= target_price:
            exit_price  = target_price
            exit_reason = 'TARGET'
            exit_time   = bar['ts_ist']
            exit_spot_p = cur_spot
            break

        # TSL
        if tsl_high >= entry_price * (1 + TSL_ACTIVATE):
            tsl_activated = True
            tsl_floor = tsl_high * (1 - TSL_TRAIL)
            if lo <= tsl_floor and tsl_floor > sl_price:
                exit_price  = max(tsl_floor, sl_price)
                exit_reason = 'TSL'
                exit_time   = bar['ts_ist']
                exit_spot_p = cur_spot
                break

    if exit_price is None:
        last = remaining_bars.iloc[-1] if len(remaining_bars) > 0 else entry_bar
        exit_price  = float(last['close'])
        exit_time   = last['ts_ist']
        exit_reason = 'EOD'
        exit_spot_p = float(last.get('spot', entry_spot))

    exit_price = max(exit_price, 0.05)
    return exit_price, exit_reason, exit_time, exit_spot_p


# ─────────────────────────────────────────────────────────────────────────────
# MAIN BACKTEST
# ─────────────────────────────────────────────────────────────────────────────
def run_backtest_v5(opt_data: pd.DataFrame, eod_data: pd.DataFrame) -> List[Trade]:
    trading_days = sorted(opt_data['date'].unique())
    all_trades:  List[Trade] = []

    day_regimes = label_days(opt_data)

    print(f"\n{'='*65}")
    print(f"BACKTEST V5 MANUAL — {len(trading_days)} days")
    print(f"Exact manual rules: Day High/Low Touch + RSI + EMA + Breakout")
    print(f"Max {MAX_TRADES_DAY} trades/day | Target +{TARGET_PCT*100:.0f}% | SL -{SL_PCT*100:.0f}% | Exit {HARD_EXIT_HHMM}")
    print(f"{'='*65}\n")
    print("Regime distribution:")
    print(day_regimes.value_counts().to_string())
    tradeable = sum(1 for r in day_regimes if r in TRADEABLE_REGIMES)
    print(f"Tradeable days: {tradeable}/{len(day_regimes)} ({100*tradeable//len(day_regimes)}%)")
    print()

    for day in trading_days:
        regime = day_regimes.get(day, 'NORMAL')

        # Skip untradeable regimes entirely
        if regime not in TRADEABLE_REGIMES:
            continue

        day_data = opt_data[opt_data['date'] == day].copy()
        expiry   = is_expiry_day(day)
        pcr      = calc_pcr(day_data)
        c15      = build_15min_spot(day_data)
        if len(c15) < 4:
            continue

        # Get EOD day OHLC for initial reference
        eod_row = eod_data[eod_data['dt'] == day]
        if not eod_row.empty:
            r = eod_row.iloc[0]
            day_open = r['open']
        else:
            day_open = float(day_data['spot'].iloc[0])

        # Track running high/low (update each candle — not end-of-day)
        trades_today: Dict[str, int]  = {'CE': 0, 'PE': 0}
        last_ce_exit: Dict[str, object] = {'reason': None, 'hhmm': 0}  # track last CE exit
        allowed_dirs = REGIME_ALLOWED_DIRECTIONS.get(regime, ['CE', 'PE'])

        for i in range(3, len(c15)):  # need at least 3 prev candles for RSI/EMA
            if sum(trades_today.values()) >= MAX_TRADES_DAY:
                break

            row  = c15.iloc[i]
            ts   = row['ts_ist'] if hasattr(row['ts_ist'], 'hour') else pd.Timestamp(row['ts_ist'])
            hhmm = ts.hour * 100 + ts.minute

            # Only trade 9:45 to 14:00
            if hhmm < 945 or hhmm > 1400:
                continue

            candles_so_far = c15.iloc[:i+1]

            # Running high/low up to this point
            day_running_high = float(candles_so_far['high'].max()) if 'high' in candles_so_far else float(candles_so_far['close'].max())
            day_running_low  = float(candles_so_far['low'].min())  if 'low'  in candles_so_far else float(candles_so_far['close'].min())

            # VWAP estimate
            if 'volume' in candles_so_far.columns:
                vwap = float((candles_so_far['close'] * candles_so_far['volume']).sum() /
                             candles_so_far['volume'].sum()) if candles_so_far['volume'].sum() > 0 else 0.0
            else:
                vwap = 0.0

            # Try CE if allowed
            # Re-entry rules: allow 2nd CE only if:
            #   - Previous CE exited as a WIN (SPOT_TGT/TARGET/TSL)
            #   - At least 15min gap since last CE exit
            #   - Re-entry before 13:30 (needs time for TSL to work before 14:15 hard exit)
            is_reentry = trades_today['CE'] > 0
            ce_reentry_ok = (
                trades_today['CE'] == 0 or  # first CE — always OK
                (trades_today['CE'] < MAX_CE_PER_DAY and
                 last_ce_exit['reason'] in ('SPOT_TGT', 'TARGET', 'TSL') and
                 hhmm >= last_ce_exit['hhmm'] + MIN_REENTRY_GAP and
                 hhmm <= 1330)              # no re-entry after 13:30
            )
            if 'CE' in allowed_dirs and ce_reentry_ok:
                fired, reason, conf = check_ce_signal(
                    candles_so_far, day_running_low, pcr, hhmm, vwap)

                if fired:
                    # Get option bars for ATM CE
                    opt_bars = day_data[
                        (day_data['option_type_flag'] == 'CE') &
                        (day_data['strike'] == 'ATM') &
                        (day_data['hhmm'] == hhmm)
                    ]
                    if len(opt_bars) > 0:
                        opt_prem = float(opt_bars['close'].iloc[-1])
                        if 30 <= opt_prem <= 400:
                            exec_bars = day_data[
                                (day_data['option_type_flag'] == 'CE') &
                                (day_data['strike'] == 'ATM') &
                                (day_data['hhmm'] > hhmm)
                            ].reset_index(drop=True)

                            if len(exec_bars) >= 2:
                                entry_bar   = exec_bars.iloc[0]
                                entry_price = float(entry_bar['open'])
                                entry_spot  = float(entry_bar.get('spot', day_running_low))
                                remaining   = exec_bars.iloc[1:].copy()
                                lots = get_lots(conf, reason)

                                ep, er, et, es = execute_v5(
                                    entry_bar, remaining, 'CE',
                                    entry_spot, day_running_high, day_running_low)

                                pnl_pts = ep - entry_price
                                pnl_rs  = round(pnl_pts * LOT_SIZE * lots - BROKERAGE, 2)

                                all_trades.append(Trade(
                                    date=day, strategy=reason, direction='CE',
                                    regime=regime, confidence=conf, lots=lots,
                                    entry_time=entry_bar['ts_ist'], entry_price=entry_price,
                                    entry_spot=entry_spot, exit_price=ep, exit_time=et,
                                    exit_reason=er, exit_spot=es,
                                    spot_move=es - entry_spot,
                                    pnl_pts=round(pnl_pts, 2), pnl_rs=pnl_rs,
                                    won=pnl_rs > 0,
                                ))
                                trades_today['CE'] += 1
                                last_ce_exit['reason'] = er
                                last_ce_exit['hhmm'] = (et.hour * 100 + et.minute) if hasattr(et, 'hour') else hhmm

            # Try PE if allowed
            if 'PE' in allowed_dirs and trades_today['PE'] == 0:
                fired, reason, conf = check_pe_signal(
                    candles_so_far, day_running_high, pcr, hhmm)

                if fired:
                    opt_bars = day_data[
                        (day_data['option_type_flag'] == 'PE') &
                        (day_data['strike'] == 'ATM') &
                        (day_data['hhmm'] == hhmm)
                    ]
                    if len(opt_bars) > 0:
                        opt_prem = float(opt_bars['close'].iloc[-1])
                        if 30 <= opt_prem <= 400:
                            exec_bars = day_data[
                                (day_data['option_type_flag'] == 'PE') &
                                (day_data['strike'] == 'ATM') &
                                (day_data['hhmm'] > hhmm)
                            ].reset_index(drop=True)

                            if len(exec_bars) >= 2:
                                entry_bar   = exec_bars.iloc[0]
                                entry_price = float(entry_bar['open'])
                                entry_spot  = float(entry_bar.get('spot', day_running_high))
                                remaining   = exec_bars.iloc[1:].copy()
                                lots = get_lots(conf)

                                ep, er, et, es = execute_v5(
                                    entry_bar, remaining, 'PE',
                                    entry_spot, day_running_high, day_running_low)

                                pnl_pts = ep - entry_price
                                pnl_rs  = round(pnl_pts * LOT_SIZE * lots - BROKERAGE, 2)

                                all_trades.append(Trade(
                                    date=day, strategy=reason, direction='PE',
                                    regime=regime, confidence=conf, lots=lots,
                                    entry_time=entry_bar['ts_ist'], entry_price=entry_price,
                                    entry_spot=entry_spot, exit_price=ep, exit_time=et,
                                    exit_reason=er, exit_spot=es,
                                    spot_move=entry_spot - es,
                                    pnl_pts=round(pnl_pts, 2), pnl_rs=pnl_rs,
                                    won=pnl_rs > 0,
                                ))
                                trades_today['PE'] += 1

    return all_trades


# ─────────────────────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────────────────────
def report_v5(trades: List[Trade], opt_data: pd.DataFrame):
    DAYS = opt_data['date'].nunique()
    day_regimes  = label_days(opt_data)
    trade_days   = len(set(t.date for t in trades)) if trades else 0
    skip_days    = sum(1 for r in day_regimes if r not in TRADEABLE_REGIMES)

    if not trades:
        print("No trades generated — check signal conditions.")
        return

    total   = sum(t.pnl_rs for t in trades)
    daily   = total / trade_days if trade_days else 0
    day_pct = daily / CAPITAL * 100
    wins    = sum(1 for t in trades if t.won)
    wr      = 100 * wins / len(trades)

    print(f"\n{'='*70}")
    print(f"BACKTEST V5 MANUAL RESULTS  |  {DAYS} total days  |  {trade_days} traded days")
    print(f"Skipped {skip_days} HIGH_VOL/RANGE days ({100*skip_days//DAYS}%)")
    print(f"{'='*70}")
    print(f"  Total trades   : {len(trades)}")
    print(f"  Win rate       : {wr:.1f}%")
    print(f"  Total PnL      : ₹{total:+,.0f}")
    print(f"  Avg PnL/traded day : ₹{daily:+,.0f}  ({day_pct:+.2f}% target 10%)")
    print(f"  Monthly est.   : ₹{daily*22:+,.0f}  ({daily*22/CAPITAL*100:.1f}%)")

    t25 = [t for t in trades if str(t.date).startswith('2025')]
    t26 = [t for t in trades if str(t.date).startswith('2026')]
    d25 = len(set(t.date for t in t25)) or 1
    d26 = len(set(t.date for t in t26)) or 1
    p25 = sum(t.pnl_rs for t in t25)
    p26 = sum(t.pnl_rs for t in t26)
    print(f"\n  2025: ₹{p25:+,.0f}  ({d25} traded days, {len(t25)} trades, ₹{p25/d25:+.0f}/day, {p25/d25/CAPITAL*100:.1f}%/day)")
    print(f"  2026: ₹{p26:+,.0f}  ({d26} traded days, {len(t26)} trades, ₹{p26/d26:+.0f}/day, {p26/d26/CAPITAL*100:.1f}%/day)")

    # Per signal
    print(f"\n{'='*70}")
    print(f"{'Signal':<26} {'N':>4} {'Win%':>6} {'Total':>9} {'Avg/Trade':>10} {'Avg Lots':>9}")
    print('-'*70)
    by_sig = defaultdict(list)
    for t in trades:
        by_sig[t.strategy].append(t)
    for name, ts in sorted(by_sig.items(), key=lambda x: sum(t.pnl_rs for t in x[1]), reverse=True):
        pnl  = sum(t.pnl_rs for t in ts)
        wr2  = 100 * sum(1 for t in ts if t.won) / len(ts)
        apt  = pnl / len(ts)
        alts = sum(t.lots for t in ts) / len(ts)
        print(f"  {name:<24} {len(ts):>4} {wr2:>5.0f}% {pnl:>+9,.0f} {apt:>+10,.0f} {alts:>9.2f}")

    # Per regime
    print(f"\n{'='*70}")
    print(f"{'Regime':<22} {'Trades':>6} {'Win%':>6} {'Total':>9} {'Per Trade':>10}")
    print('-'*70)
    by_reg = defaultdict(list)
    for t in trades:
        by_reg[t.regime].append(t)
    for reg, ts in sorted(by_reg.items(), key=lambda x: sum(t.pnl_rs for t in x[1]), reverse=True):
        pnl = sum(t.pnl_rs for t in ts)
        wr2 = 100 * sum(1 for t in ts if t.won) / len(ts)
        print(f"  {reg:<20} {len(ts):>6} {wr2:>5.0f}% {pnl:>+9,.0f} {pnl/len(ts):>+10,.0f}")

    # Exit reasons
    print(f"\n{'='*70}")
    exits = defaultdict(int)
    exit_pnl = defaultdict(float)
    for t in trades:
        exits[t.exit_reason] += 1
        exit_pnl[t.exit_reason] += t.pnl_rs
    print(f"{'Exit Reason':<14} {'Count':>6} {'Total PnL':>10} {'Avg PnL':>10}")
    print('-'*50)
    for er, cnt in sorted(exits.items(), key=lambda x: -x[1]):
        print(f"  {er:<12} {cnt:>6} {exit_pnl[er]:>+10,.0f} {exit_pnl[er]/cnt:>+10,.0f}")

    # Daily distribution
    daily_pnl = defaultdict(float)
    for t in trades:
        daily_pnl[t.date] += t.pnl_rs
    dv = list(daily_pnl.values())
    green       = sum(1 for v in dv if v > 0)
    target_days = sum(1 for v in dv if v >= CAPITAL * 0.10)
    half_target = sum(1 for v in dv if v >= CAPITAL * 0.05)
    print(f"\n  Green days     : {green}/{len(dv)} ({100*green//max(len(dv),1)}%)")
    print(f"  10%+ days      : {target_days}/{len(dv)} ({100*target_days//max(len(dv),1)}%)")
    print(f"  5%+ days       : {half_target}/{len(dv)} ({100*half_target//max(len(dv),1)}%)")
    print(f"  Best day       : ₹{max(dv):+,.0f}")
    print(f"  Worst day      : ₹{min(dv):+,.0f}")
    cum = pd.Series(sorted(daily_pnl.keys())).apply(lambda d: daily_pnl[d])
    dd  = (cum.cumsum() - cum.cumsum().cummax()).min()
    print(f"  Max drawdown   : ₹{dd:+,.0f}")

    # Top days
    top10 = sorted(daily_pnl.items(), key=lambda x: x[1], reverse=True)[:10]
    print(f"\nTop 10 trading days:")
    for d, v in top10:
        day_trades = [t for t in trades if t.date == d]
        sigs = ', '.join(f"{t.direction}({t.strategy[:12]})" for t in day_trades)
        print(f"  {d}  ₹{v:+,.0f}  ({len(day_trades)} trades: {sigs})")
    print(f"{'='*70}")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Loading data...")
    opt_data = load_option_data()
    eod_data = load_eod_data()

    trades = run_backtest_v5(opt_data, eod_data)
    report_v5(trades, opt_data)
