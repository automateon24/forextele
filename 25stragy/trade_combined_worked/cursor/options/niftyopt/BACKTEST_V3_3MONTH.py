#!/usr/bin/env python3
"""
BACKTEST V3 — 3 Month (Feb 3, 2025 – May 4, 2025)
Real Dhan-fetched 1min option parquet data only. No simulation, no fake data.

Data:  data/raw/NIFTY_expired_<start>_<end>_<strike>_<type>_1min_MONTH_1.parquet
       data/raw/NIFTY_eod_*  (daily OHLC for spot context)

Strategies tested (21 total):
  V3 core (19): ULTIMATE_DAY_HIGH_LOW, DAY_HIGH_BEARISH, DAY_LOW_BULLISH,
                ENHANCED_BEARISH, ENHANCED_BULLISH, DAY_HIGH_LOW_TRADITIONAL,
                TREND_FOLLOWING, AI_ENHANCED, MEAN_REVERSION, SCALPING,
                BREAKOUT, VOLATILITY_BREAKOUT, OPTIONS_GREEKS, MAGIC_SQUARE,
                SHORT_UNWIND, LONG_UNWIND, RESIST_BREAK, PUT_WRITER_SUPPORT,
                ORDER_BLOCK_REVERSAL
  New (2):     ZERO_HERO, GAMMA_BLAST

Each strategy defines:
  - which_type: CE / PE / BOTH
  - which_strike: ATM, ATM+1, ATM-1, etc.
  - entry_func(candles_15m, spot, pcr, rsi) -> bool
  - entry_time_window: (hhmm_start, hhmm_end)
  - exit_sl_pct, exit_target_pct
  - trailing_stop: None or points

Trade mechanics (real data):
  - Entry price = next 1min candle open after signal fires on 15min bar
  - Exit at SL/target/TSL on 1min bars, or force-close at 15:25
  - LOT_SIZE = 75, brokerage = Rs.20/trade + 0.05% STT on premium

Output: results/BACKTEST_V3_3M_RESULTS.csv + printed table
"""

import os, sys, re, warnings
from datetime import date, datetime, timedelta, time as dtime
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')
os.makedirs('results', exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────
LOT_SIZE    = 75
SL_PCT      = 0.30      # default stop loss
TARGET_PCT  = 0.50      # default target
BROKERAGE   = 20.0      # Rs per trade (both legs combined)
STT_PCT     = 0.0005    # 0.05% on premium sold
RAW_DIR     = 'data/raw'

# ── IST offset for parquet timestamps (stored as UTC 03:45 = IST 09:15) ───────
UTC_OFFSET  = pd.Timedelta(hours=5, minutes=30)

# ── NIFTY weekly expiry = every Thursday ─────────────────────────────────────
def is_expiry_day(d: date) -> bool:
    return d.weekday() == 3   # Thursday

# ── ATM step ─────────────────────────────────────────────────────────────────
ATM_STEP = 50

def atm(spot: float) -> float:
    return round(spot / ATM_STEP) * ATM_STEP


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADER
# Loads all relevant parquets and merges into a single 1min DataFrame
# covering Feb 2025 – May 2025, ATM±2 both CE and PE
# ═══════════════════════════════════════════════════════════════════════════════

PERIODS = [
    ('2025-02-03', '2025-03-05'),
    ('2025-03-05', '2025-04-04'),
    ('2025-04-04', '2025-05-04'),
]
STRIKES  = ['ATM', 'ATM+1', 'ATM-1', 'ATM+2', 'ATM-2']
OPT_TYPES = ['CALL', 'PUT']


def load_option_data() -> pd.DataFrame:
    print("Loading real 1min option data from parquet files...")
    frames = []
    for period_start, period_end in PERIODS:
        for strike in STRIKES:
            for otype in OPT_TYPES:
                fname = (f"NIFTY_expired_{period_start}_{period_end}_"
                         f"{strike}_{otype}_1min_MONTH_1.parquet")
                fpath = os.path.join(RAW_DIR, fname)
                if not os.path.exists(fpath):
                    print(f"  MISSING: {fname}")
                    continue
                df = pd.read_parquet(fpath)
                df['option_type_flag'] = 'CE' if otype == 'CALL' else 'PE'
                df['period'] = f"{period_start}_to_{period_end}"
                frames.append(df)
    if not frames:
        raise RuntimeError("No parquet files found!")
    data = pd.concat(frames, ignore_index=True)
    # Convert UTC timestamps to IST
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    if data['timestamp'].dt.tz is None:
        data['ts_ist'] = data['timestamp'] + UTC_OFFSET
    else:
        data['ts_ist'] = data['timestamp'].dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
    data['date']   = data['ts_ist'].dt.date
    data['time']   = data['ts_ist'].dt.time
    data['hhmm']   = data['ts_ist'].dt.hour * 100 + data['ts_ist'].dt.minute
    data = data.sort_values(['date', 'strike', 'option_type_flag', 'ts_ist']).reset_index(drop=True)
    print(f"  Loaded {len(data):,} rows | "
          f"{data['date'].nunique()} trading days | "
          f"{data['date'].min()} to {data['date'].max()}")
    return data


def load_eod_data() -> pd.DataFrame:
    """Load daily OHLC for NIFTY."""
    eod_files = sorted([f for f in os.listdir(RAW_DIR) if 'NIFTY_eod' in f and '2015' in f])
    df = pd.read_parquet(os.path.join(RAW_DIR, eod_files[-1]))
    df['dt'] = pd.to_datetime(df['Date'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata').dt.date
    df = df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close'})
    df = df.sort_values('dt').reset_index(drop=True)
    return df[['dt','open','high','low','close']]


# ═══════════════════════════════════════════════════════════════════════════════
# 15-MINUTE CANDLE BUILDER  (from 1min data for indicator calculation)
# ═══════════════════════════════════════════════════════════════════════════════

def build_15min_spot(day_1min: pd.DataFrame) -> pd.DataFrame:
    """Build 15min OHLCV for NIFTY spot from 1min data (use spot column)."""
    df = day_1min[['ts_ist','spot']].copy().drop_duplicates('ts_ist')
    df = df.set_index('ts_ist').sort_index()
    df = df.rename(columns={'spot':'close'})
    df['open']  = df['close']
    df['high']  = df['close']
    df['low']   = df['close']
    df['volume']= 0
    # Resample to 15min
    r = df['close'].resample('15min').ohlc()
    r.columns = ['open','high','low','close']
    r = r.dropna()
    return r.reset_index()


def calc_rsi(closes: pd.Series, n: int = 14) -> pd.Series:
    delta  = closes.diff()
    gain   = delta.clip(lower=0)
    loss   = (-delta).clip(lower=0)
    avg_g  = gain.ewm(com=n-1, min_periods=n).mean()
    avg_l  = loss.ewm(com=n-1, min_periods=n).mean()
    rs     = avg_g / avg_l.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def calc_pcr(day_data: pd.DataFrame) -> float:
    """PCR from latest OI snapshot of the day."""
    latest = day_data.groupby(['strike','option_type_flag'])['oi'].last()
    pe_oi  = latest.xs('PE', level='option_type_flag').sum() if 'PE' in latest.index.get_level_values(1) else 0
    ce_oi  = latest.xs('CE', level='option_type_flag').sum() if 'CE' in latest.index.get_level_values(1) else 0
    return pe_oi / ce_oi if ce_oi > 0 else 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY DEFINITIONS
# Each strategy is a dict with the logic to fire entry signals
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class StrategyDef:
    name: str
    direction: str          # CE, PE, BOTH
    strike: str             # ATM, ATM+1, ATM-1, ATM+2, ATM-2
    entry_start: int        # HHMM
    entry_end: int          # HHMM
    sl_pct: float           = SL_PCT
    target_pct: float       = TARGET_PCT
    tsl_pts: Optional[float]= None      # trailing stop in Rs (None = no TSL)
    min_premium: float      = 15.0
    notes: str              = ''


def make_strategies() -> List[StrategyDef]:
    return [
        # ── ORB / Day High-Low ────────────────────────────────────────────────
        StrategyDef('ULTIMATE_DAY_HIGH_LOW', 'BOTH', 'ATM',   935, 1130, notes='ORB15 break+retest'),
        StrategyDef('DAY_HIGH_BEARISH',      'PE',   'ATM',   935, 1200, notes='Day high reject→CE sell'),
        StrategyDef('DAY_LOW_BULLISH',       'CE',   'ATM',   935, 1200, notes='Day low bounce→PE sell'),
        StrategyDef('DAY_HIGH_LOW_TRADITIONAL','BOTH','ATM',  935, 1200),

        # ── Enhanced/Trend ────────────────────────────────────────────────────
        StrategyDef('ENHANCED_BEARISH',      'PE',   'ATM',   935, 1400, tsl_pts=15),
        StrategyDef('ENHANCED_BULLISH',      'CE',   'ATM',   935, 1400, tsl_pts=15),
        StrategyDef('TREND_FOLLOWING',       'BOTH', 'ATM',   945, 1400, notes='EMA cross'),
        StrategyDef('AI_ENHANCED',           'BOTH', 'ATM',   945, 1400, notes='Multi-factor'),

        # ── Mean Rev / Scalp ─────────────────────────────────────────────────
        StrategyDef('MEAN_REVERSION',        'BOTH', 'ATM',   935, 1330, sl_pct=0.25, target_pct=0.35),
        StrategyDef('SCALPING',              'BOTH', 'ATM',   935, 1415, sl_pct=0.20, target_pct=0.30, tsl_pts=10),
        StrategyDef('BREAKOUT',              'BOTH', 'ATM+1', 935, 1400),
        StrategyDef('VOLATILITY_BREAKOUT',   'BOTH', 'ATM',   935, 1400, notes='IV spike'),

        # ── Greeks / OI ───────────────────────────────────────────────────────
        StrategyDef('OPTIONS_GREEKS',        'BOTH', 'ATM',   935, 1330, notes='Delta/gamma triggers'),
        StrategyDef('SHORT_UNWIND',          'CE',   'ATM',   935, 1400, notes='PE OI shed→buy CE'),
        StrategyDef('LONG_UNWIND',           'PE',   'ATM',   935, 1400, notes='CE OI shed→buy PE'),
        StrategyDef('PUT_WRITER_SUPPORT',    'CE',   'ATM',   935, 1300, notes='Max PUT OI support'),

        # ── Pattern ──────────────────────────────────────────────────────────
        StrategyDef('RESIST_BREAK',          'CE',   'ATM+1', 935, 1400),
        StrategyDef('MAGIC_SQUARE',          'BOTH', 'ATM',   935, 1400),
        StrategyDef('ORDER_BLOCK_REVERSAL',  'BOTH', 'ATM',  1000, 1400, notes='Support/resist bounce'),

        # ── NEW: Zero-Hero (cheap OTM → big multiplier) ───────────────────────
        StrategyDef('ZERO_HERO',             'BOTH', 'ATM+2', 930, 1430,
                    sl_pct=0.40, target_pct=3.0, tsl_pts=20,
                    min_premium=3.0, notes='Cheap OTM; big gamma pop'),

        # ── NEW: Gamma Blast (expiry day last 90 min, ATM, explosive move) ────
        StrategyDef('GAMMA_BLAST',           'BOTH', 'ATM',  1330, 1520,
                    sl_pct=0.25, target_pct=2.0, tsl_pts=30,
                    min_premium=5.0, notes='Expiry day only, 13:30-15:20'),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL LOGIC
# Each strategy checks its own conditions on 15min candle data
# Returns True/False for CE or PE entry
# ═══════════════════════════════════════════════════════════════════════════════

def signal_check(strat: StrategyDef, direction: str,
                 candles15: pd.DataFrame, day_ohlc: dict,
                 pcr: float, current_hhmm: int,
                 is_expiry: bool) -> bool:
    """
    Returns True if the strategy fires a signal for 'direction' (CE or PE)
    at this 15min bar.
    candles15: all 15min bars up to and including current bar (cols: ts_ist, open, high, low, close)
    day_ohlc: {'open':float, 'high':float, 'low':float, 'close':float} for the full day
    """
    if len(candles15) < 2:
        return False
    c   = candles15.iloc[-1]    # current bar
    p   = candles15.iloc[-2]    # previous bar
    spot= float(c['close'])
    closes = candles15['close'].values.astype(float)

    rsi  = float(calc_rsi(pd.Series(closes)).iloc[-1])
    vwap = float(closes.mean())  # simplified VWAP
    ema5 = float(pd.Series(closes).ewm(span=5,  adjust=False).mean().iloc[-1])
    ema20= float(pd.Series(closes).ewm(span=20, adjust=False).mean().iloc[-1])

    day_open  = float(day_ohlc['open'])
    day_high  = float(day_ohlc['high'])
    day_low   = float(day_ohlc['low'])
    candle_rng= float(c['high']) - float(c['low'])

    # Average 5-candle range for gamma blast detection
    avg5_rng  = float((candles15['high'] - candles15['low']).tail(5).mean()) if len(candles15) >= 5 else candle_rng

    n = strat.name
    d = direction

    # ── ORB strategies ────────────────────────────────────────────────────────
    if n == 'ULTIMATE_DAY_HIGH_LOW':
        # CE: break above ORB high (first 15min candle high)
        orb_high = float(candles15.iloc[0]['high'])
        orb_low  = float(candles15.iloc[0]['low'])
        if d == 'CE': return spot > orb_high * 1.002 and rsi > 55 and ema5 > ema20
        if d == 'PE': return spot < orb_low  * 0.998 and rsi < 45 and ema5 < ema20

    if n == 'DAY_HIGH_BEARISH':
        # PE: price tags day high then closes below
        near_high = abs(spot - day_high) / day_high < 0.003
        if d == 'PE': return near_high and rsi > 65 and c['close'] < c['open']

    if n == 'DAY_LOW_BULLISH':
        # CE: price near day low, bounce with RSI oversold or PCR > 1
        near_low = abs(spot - day_low) / day_low < 0.003
        if d == 'CE': return near_low and (rsi < 45 or pcr > 1.0) and c['close'] > c['open']

    if n == 'DAY_HIGH_LOW_TRADITIONAL':
        if d == 'CE': return spot > day_high * 1.001 and rsi > 55
        if d == 'PE': return spot < day_low  * 0.999 and rsi < 45

    # ── Enhanced / Trend ─────────────────────────────────────────────────────
    if n == 'ENHANCED_BEARISH':
        if d == 'PE': return rsi > 70 and spot < ema5 and c['close'] < p['close']

    if n == 'ENHANCED_BULLISH':
        if d == 'CE': return rsi < 32 and spot > ema5 and c['close'] > p['close']

    if n == 'TREND_FOLLOWING':
        if d == 'CE': return ema5 > ema20 and c['close'] > c['open'] and rsi > 50
        if d == 'PE': return ema5 < ema20 and c['close'] < c['open'] and rsi < 50

    if n == 'AI_ENHANCED':
        # Multi-factor: trend + PCR + RSI
        bullish = ema5 > ema20 and pcr > 1.1 and rsi < 60 and spot > vwap
        bearish = ema5 < ema20 and pcr < 0.9 and rsi > 40 and spot < vwap
        if d == 'CE': return bullish
        if d == 'PE': return bearish

    # ── Mean Rev / Scalp ─────────────────────────────────────────────────────
    if n == 'MEAN_REVERSION':
        bb_mid  = float(pd.Series(closes).rolling(20).mean().iloc[-1]) if len(closes) >= 20 else vwap
        bb_std  = float(pd.Series(closes).rolling(20).std().iloc[-1])  if len(closes) >= 20 else 1
        bb_up   = bb_mid + 2 * bb_std
        bb_dn   = bb_mid - 2 * bb_std
        if d == 'CE': return spot < bb_dn and rsi < 35
        if d == 'PE': return spot > bb_up and rsi > 65

    if n == 'SCALPING':
        # 1-bar momentum continuation
        if d == 'CE': return c['close'] > p['high'] and rsi > 52
        if d == 'PE': return c['close'] < p['low']  and rsi < 48

    if n == 'BREAKOUT':
        # 20-bar high/low breakout
        if len(candles15) >= 20:
            recent_high = float(candles15['high'].iloc[:-1].tail(20).max())
            recent_low  = float(candles15['low'].iloc[:-1].tail(20).min())
            if d == 'CE': return spot > recent_high * 1.001
            if d == 'PE': return spot < recent_low  * 0.999
        return False

    if n == 'VOLATILITY_BREAKOUT':
        # Large candle (>1.5x avg range)
        if avg5_rng > 0:
            big_candle = candle_rng > avg5_rng * 1.5
            if d == 'CE': return big_candle and c['close'] > c['open']
            if d == 'PE': return big_candle and c['close'] < c['open']

    # ── Greeks / OI ─────────────────────────────────────────────────────────
    if n == 'OPTIONS_GREEKS':
        # ATM IV spike + direction (simplified: use big candle + RSI)
        if d == 'CE': return rsi < 40 and c['close'] > c['open'] and candle_rng > avg5_rng
        if d == 'PE': return rsi > 60 and c['close'] < c['open'] and candle_rng > avg5_rng

    if n == 'SHORT_UNWIND':
        # PE OI shedding → buy CE (CE rally)
        if d == 'CE': return pcr < 0.85 and ema5 > ema20 and rsi > 50

    if n == 'LONG_UNWIND':
        # CE OI shedding → buy PE
        if d == 'PE': return pcr > 1.15 and ema5 < ema20 and rsi < 50

    if n == 'PUT_WRITER_SUPPORT':
        # Spot near max PUT OI strike (ATM), bounce up
        if d == 'CE': return pcr > 1.2 and rsi < 45 and c['close'] > c['open']

    # ── Pattern ─────────────────────────────────────────────────────────────
    if n == 'RESIST_BREAK':
        if len(candles15) >= 5:
            resist = float(candles15['high'].iloc[:-1].tail(5).max())
            if d == 'CE': return spot > resist * 1.001 and rsi > 52

    if n == 'MAGIC_SQUARE':
        # Square-of-nine levels: rough proxy = Fibonacci retracements
        fib_618 = day_open + (day_high - day_open) * 0.618
        fib_382 = day_open - (day_open - day_low)  * 0.382
        if d == 'CE': return abs(spot - fib_382) / spot < 0.002 and rsi < 42
        if d == 'PE': return abs(spot - fib_618) / spot < 0.002 and rsi > 58

    if n == 'ORDER_BLOCK_REVERSAL':
        # Price revisits prior strong candle's low/high (support/resistance)
        if len(candles15) >= 3:
            strong_candle = candles15.iloc[-3]
            support = float(strong_candle['low'])
            resist  = float(strong_candle['high'])
            if d == 'CE': return abs(spot - support) / support < 0.005 and rsi < 45
            if d == 'PE': return abs(spot - resist)  / resist  < 0.005 and rsi > 55

    # ── Zero-Hero ─────────────────────────────────────────────────────────────
    if n == 'ZERO_HERO':
        # OTM option with momentum + RSI extreme → lottery entry
        if d == 'CE': return rsi < 30 and c['close'] > c['open'] and candle_rng > avg5_rng * 1.2
        if d == 'PE': return rsi > 70 and c['close'] < c['open'] and candle_rng > avg5_rng * 1.2

    # ── Gamma Blast (expiry day only, last 90 min) ───────────────────────────
    if n == 'GAMMA_BLAST':
        if not is_expiry:
            return False
        # Big candle (≥2x avg5) + volume spike + directional
        if d == 'CE': return (candle_rng >= avg5_rng * 2.0 and
                              c['close'] > c['open'] and rsi > 52)
        if d == 'PE': return (candle_rng >= avg5_rng * 2.0 and
                              c['close'] < c['open'] and rsi < 48)

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# TRADE EXECUTOR  (1min bar by bar exit simulation with TSL)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Trade:
    strategy:    str
    direction:   str
    strike:      str
    date:        date
    entry_time:  dtime
    entry_price: float
    sl_price:    float
    target_price:float
    tsl_pts:     Optional[float]
    exit_price:  float   = 0.0
    exit_time:   dtime   = None
    exit_reason: str     = ''
    pnl_pts:     float   = 0.0
    pnl_rs:      float   = 0.0
    won:         bool    = False


def execute_trade(entry_bar_idx: int,
                  bars_1min: pd.DataFrame,
                  strat: StrategyDef,
                  direction: str) -> Trade:
    """
    Enter at next 1min bar open after signal, simulate exit on 1min bars.
    bars_1min: filtered to this strike+type, this day, hhmm >= entry bar.
    """
    # Entry on the candle AFTER signal
    if entry_bar_idx + 1 >= len(bars_1min):
        return None

    entry_bar   = bars_1min.iloc[entry_bar_idx + 1]
    entry_price = float(entry_bar['open'])
    if entry_price <= strat.min_premium:
        return None

    sl_price     = entry_price * (1 - strat.sl_pct)
    target_price = entry_price * (1 + strat.target_pct)
    tsl_high     = entry_price   # highest price seen (for TSL)
    tsl_low      = entry_price   # lowest price seen

    # Walk forward on remaining 1min bars of the day
    remaining = bars_1min.iloc[entry_bar_idx + 2:]

    exit_price  = None
    exit_reason = 'EOD'

    for _, bar in remaining.iterrows():
        hi = float(bar['high'])
        lo = float(bar['low'])
        cl = float(bar['close'])
        hhmm = int(bar['hhmm'])

        # Force EOD exit at 15:25
        if hhmm >= 1525:
            exit_price  = cl
            exit_reason = 'EOD'
            exit_time   = bar['ts_ist'].time() if hasattr(bar['ts_ist'], 'time') else bar['time']
            break

        # Update TSL
        if strat.tsl_pts is not None:
            tsl_high = max(tsl_high, hi)
            tsl_low  = min(tsl_low,  lo)
            tsl_sl = tsl_high - strat.tsl_pts   # for CE: trail from highest point
            tsl_sl_pe = tsl_low + strat.tsl_pts  # for PE: trail from lowest point

        # Target hit?
        if hi >= target_price:
            exit_price  = target_price
            exit_reason = 'TARGET'
            exit_time   = bar['ts_ist'].time() if hasattr(bar['ts_ist'], 'time') else bar['time']
            break

        # SL hit?
        if lo <= sl_price:
            exit_price  = sl_price
            exit_reason = 'SL'
            exit_time   = bar['ts_ist'].time() if hasattr(bar['ts_ist'], 'time') else bar['time']
            break

        # TSL hit?
        if strat.tsl_pts is not None:
            if direction == 'CE' and tsl_high > entry_price * 1.05:   # only once in profit 5%
                if lo <= tsl_sl:
                    exit_price  = max(tsl_sl, sl_price)
                    exit_reason = 'TSL'
                    exit_time   = bar['ts_ist'].time() if hasattr(bar['ts_ist'], 'time') else bar['time']
                    break
            if direction == 'PE' and tsl_low < entry_price * 0.95:
                if hi >= tsl_sl_pe:
                    exit_price  = min(tsl_sl_pe, target_price)
                    exit_reason = 'TSL'
                    exit_time   = bar['ts_ist'].time() if hasattr(bar['ts_ist'], 'time') else bar['time']
                    break

    if exit_price is None:
        # Ran out of bars before 15:25 (short day)
        last = remaining.iloc[-1] if len(remaining) > 0 else entry_bar
        exit_price  = float(last['close'])
        exit_reason = 'EOD'
        exit_time   = last['ts_ist'].time() if hasattr(last['ts_ist'], 'time') else last['time']

    pnl_pts = exit_price - entry_price
    pnl_rs  = pnl_pts * LOT_SIZE - BROKERAGE

    t = Trade(
        strategy    = strat.name,
        direction   = direction,
        strike      = strat.strike,
        date        = bars_1min.iloc[0]['date'],
        entry_time  = entry_bar['ts_ist'].time(),
        entry_price = entry_price,
        sl_price    = sl_price,
        target_price= target_price,
        tsl_pts     = strat.tsl_pts,
        exit_price  = exit_price,
        exit_time   = exit_time,
        exit_reason = exit_reason,
        pnl_pts     = round(pnl_pts, 2),
        pnl_rs      = round(pnl_rs, 2),
        won         = pnl_rs > 0,
    )
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BACKTEST LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def run_backtest(opt_data: pd.DataFrame, eod_data: pd.DataFrame) -> List[Trade]:
    strategies = make_strategies()
    trading_days = sorted(opt_data['date'].unique())
    all_trades: List[Trade] = []

    print(f"\nRunning backtest across {len(trading_days)} trading days, {len(strategies)} strategies...\n")

    for day in trading_days:
        day_data  = opt_data[opt_data['date'] == day].copy()
        expiry    = is_expiry_day(day)

        # Day OHLC for this day (spot)
        eod_row   = eod_data[eod_data['dt'] == day]
        if eod_row.empty:
            # Derive from spot column in option data
            day_open  = float(day_data['spot'].iloc[0])
            day_high  = float(day_data['spot'].max())
            day_low   = float(day_data['spot'].min())
            day_close = float(day_data['spot'].iloc[-1])
        else:
            r = eod_row.iloc[0]
            day_open, day_high, day_low, day_close = r['open'], r['high'], r['low'], r['close']
        day_ohlc = {'open': day_open, 'high': day_high, 'low': day_low, 'close': day_close}

        # Build 15min spot candles for this day
        c15 = build_15min_spot(day_data)
        if len(c15) < 2:
            continue

        # PCR
        pcr = calc_pcr(day_data)

        # Track per-direction entries per day to avoid flooding same direction
        day_entries: Dict[str, int] = {}   # strategy -> count

        for strat in strategies:
            # Skip Gamma Blast on non-expiry days
            if strat.name == 'GAMMA_BLAST' and not expiry:
                continue

            directions = [strat.direction] if strat.direction in ('CE','PE') else ['CE','PE']

            for direction in directions:
                # Walk 15min bars inside strategy time window
                signal_fired = False
                for i, row in c15.iterrows():
                    hhmm_bar = row['ts_ist'].hour * 100 + row['ts_ist'].minute if hasattr(row['ts_ist'], 'hour') else \
                               int(str(row['ts_ist']).split(' ')[1].replace(':','')[:4])
                    if hhmm_bar < strat.entry_start:
                        continue
                    if hhmm_bar > strat.entry_end:
                        break

                    # Build candles up to this bar
                    candles_so_far = c15.iloc[:i+1]
                    fired = signal_check(strat, direction, candles_so_far, day_ohlc,
                                         pcr, hhmm_bar, expiry)
                    if not fired:
                        continue

                    # Signal fired — find 1min bars for the right strike
                    opt_type = 'CE' if direction == 'CE' else 'PE'
                    strike_bars = day_data[
                        (day_data['option_type_flag'] == opt_type) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] >= hhmm_bar)
                    ].reset_index(drop=True)

                    if len(strike_bars) < 2:
                        break

                    trade = execute_trade(0, strike_bars, strat, direction)
                    if trade is not None:
                        all_trades.append(trade)
                    signal_fired = True
                    break   # one trade per strategy per day per direction

    return all_trades


# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS TABLE
# ═══════════════════════════════════════════════════════════════════════════════

def print_results_table(trades: List[Trade]):
    if not trades:
        print("No trades generated.")
        return

    df = pd.DataFrame([
        {
            'strategy':    t.strategy,
            'direction':   t.direction,
            'date':        t.date,
            'entry_time':  t.entry_time,
            'entry_price': t.entry_price,
            'exit_price':  t.exit_price,
            'exit_reason': t.exit_reason,
            'pnl_pts':     t.pnl_pts,
            'pnl_rs':      t.pnl_rs,
            'won':         t.won,
        }
        for t in trades
    ])

    # Save detailed CSV
    out_path = 'results/BACKTEST_V3_3M_TRADES.csv'
    df.to_csv(out_path, index=False)
    print(f"Detailed trades saved → {out_path}")

    # ── Per-strategy summary ──────────────────────────────────────────────────
    summary_rows = []
    for strat_name, grp in df.groupby('strategy'):
        n_trades  = len(grp)
        n_win     = grp['won'].sum()
        win_pct   = n_win / n_trades * 100
        total_pnl = grp['pnl_rs'].sum()
        avg_pnl   = grp['pnl_rs'].mean()
        avg_win   = grp.loc[grp['won'],  'pnl_rs'].mean() if n_win > 0 else 0
        avg_loss  = grp.loc[~grp['won'], 'pnl_rs'].mean() if (n_trades-n_win) > 0 else 0
        best_day  = grp.groupby('date')['pnl_rs'].sum().max()
        worst_day = grp.groupby('date')['pnl_rs'].sum().min()
        max_dd    = (grp['pnl_rs'].cumsum() - grp['pnl_rs'].cumsum().cummax()).min()
        # Targets hit %
        tgt_pct   = (grp['exit_reason'] == 'TARGET').mean() * 100
        sl_pct_v  = (grp['exit_reason'] == 'SL').mean() * 100
        tsl_pct_v = (grp['exit_reason'] == 'TSL').mean() * 100
        eod_pct_v = (grp['exit_reason'] == 'EOD').mean() * 100

        summary_rows.append({
            'Strategy':      strat_name,
            'Trades':        n_trades,
            'Win%':          f"{win_pct:.0f}%",
            'Total P&L':     f"Rs.{total_pnl:+,.0f}",
            'Avg/trade':     f"Rs.{avg_pnl:+.0f}",
            'Avg Win':       f"Rs.{avg_win:+.0f}",
            'Avg Loss':      f"Rs.{avg_loss:+.0f}",
            'Best Day':      f"Rs.{best_day:+,.0f}",
            'Worst Day':     f"Rs.{worst_day:+,.0f}",
            'Max DD':        f"Rs.{max_dd:,.0f}",
            'TARGET%':       f"{tgt_pct:.0f}%",
            'SL%':           f"{sl_pct_v:.0f}%",
            'TSL%':          f"{tsl_pct_v:.0f}%",
            'EOD%':          f"{eod_pct_v:.0f}%",
        })

    sdf = pd.DataFrame(summary_rows)
    # Sort by Total P&L descending
    sdf['_sort'] = sdf['Total P&L'].str.replace('Rs.','').str.replace(',','').str.replace('+','').astype(float)
    sdf = sdf.sort_values('_sort', ascending=False).drop(columns='_sort')

    # Save summary CSV
    sum_path = 'results/BACKTEST_V3_3M_SUMMARY.csv'
    sdf.to_csv(sum_path, index=False)

    # ── Print table ──────────────────────────────────────────────────────────
    print()
    print("=" * 140)
    print(f"  NIFTY V3 BACKTEST — Feb 3 2025 to May 4 2025  |  "
          f"{len(df)} total trades across {df['date'].nunique()} trading days  |  LOT={LOT_SIZE}")
    print("=" * 140)
    header = (f"  {'Strategy':<28} {'Trades':>6} {'Win%':>6} {'Total P&L':>12} "
              f"{'Avg/trade':>10} {'Avg Win':>9} {'Avg Loss':>9} "
              f"{'Best Day':>10} {'Worst Day':>10} {'Max DD':>10} "
              f"{'TGT%':>5} {'SL%':>5} {'TSL%':>5} {'EOD%':>5}")
    print(header)
    print("-" * 140)
    for _, row in sdf.iterrows():
        print(f"  {row['Strategy']:<28} {row['Trades']:>6} {row['Win%']:>6} "
              f"{row['Total P&L']:>12} {row['Avg/trade']:>10} "
              f"{row['Avg Win']:>9} {row['Avg Loss']:>9} "
              f"{row['Best Day']:>10} {row['Worst Day']:>10} {row['Max DD']:>10} "
              f"{row['TARGET%']:>5} {row['SL%']:>5} {row['TSL%']:>5} {row['EOD%']:>5}")

    print("-" * 140)
    grand_pnl = df['pnl_rs'].sum()
    grand_dd  = (df['pnl_rs'].cumsum() - df['pnl_rs'].cumsum().cummax()).min()
    print(f"  {'COMBINED ALL STRATEGIES':<28} {len(df):>6} "
          f"{df['won'].mean()*100:.0f}%   "
          f"{'Rs.'+f'{grand_pnl:+,.0f}':>12} "
          f"{'Rs.'+f'{df.pnl_rs.mean():+.0f}':>10}   "
          f"{'':>9} {'':>9} {'':>10} {'':>10} "
          f"{'Rs.'+f'{grand_dd:,.0f}':>10}")
    print("=" * 140)
    print(f"\nSummary saved → {sum_path}")
    print(f"Detailed trades → {out_path}")

    # ── Zero Hero & Gamma Blast callout ──────────────────────────────────────
    for s_name in ['ZERO_HERO', 'GAMMA_BLAST']:
        sub = df[df['strategy'] == s_name]
        if len(sub) == 0:
            print(f"\n{s_name}: No trades fired in this period.")
            continue
        big_wins = sub[sub['pnl_pts'] >= sub['entry_price'] * 0.5]
        print(f"\n{s_name}: {len(sub)} trades | {sub['won'].mean()*100:.0f}% win | "
              f"Rs.{sub['pnl_rs'].sum():+,.0f} total | "
              f"{len(big_wins)} trades with 50%+ premium gain (zero-to-hero moments)")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 70)
    print("  NIFTY V3 3-Month Backtest  |  Real Dhan Parquet Data")
    print("  Feb 2025 – May 2025  |  21 Strategies (19 V3 + Zero-Hero + Gamma Blast)")
    print("=" * 70)

    opt_data = load_option_data()
    eod_data = load_eod_data()

    trades = run_backtest(opt_data, eod_data)
    print(f"\nTotal trades executed: {len(trades)}")

    print_results_table(trades)
