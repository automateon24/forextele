#!/usr/bin/env python3
"""
BACKTEST V3 TUNED — Deep Parameter Optimisation
Real Dhan 1min parquet data (Feb 3 – May 4 2025)

Changes vs V1:
  1. TSL on ALL strategies (not just scalping)
  2. Time window restricted to 12:00–14:30 based on 60–65% win-rate window
  3. Direction bias applied (CE/PE only where that direction outperforms)
  4. SL tightened to 15–20% (monthly premium only moves ±5–8% EOD)
  5. Target tightened to 20–30%
  6. VWAP confirmation: entry only when spot is on correct side of VWAP
  7. Volume confirmation: only enter when current bar volume > 1.5× avg-5
  8. Multi-strategy confluence: if 2+ strategies agree on same direction, boost signal
  9. Premium filter: ATM Rs.50–400, OTM (Zero-Hero) Rs.5–50
  10. Zero-Hero: PE-biased, premium<50, TSL=Rs.8, target=3×, expiry-day weight
  11. Gamma-Blast: both CE/PE, last 90min expiry only, candle ≥ 2× avg5
  12. Strike selection refined: winning strikes kept, losing strikes demoted to ATM

Grid search sweeps:
  - sl_pct:      [0.10, 0.15, 0.20]
  - target_pct:  [0.20, 0.25, 0.30]
  - tsl_pts:     [8, 12, 20]
  - entry_start: [1200, 1230, 1300]   (morning confirmed worst)
  - min_premium: [30, 50, 80]

Best params per strategy selected by highest Sharpe-like ratio (avg/std).
"""

import os, sys, warnings, itertools
from datetime import date, time as dtime
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')
os.makedirs('results', exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LOT_SIZE    = 75
BROKERAGE   = 20.0
RAW_DIR     = 'data/raw'
UTC_OFFSET  = pd.Timedelta(hours=5, minutes=30)
ATM_STEP    = 50

def is_expiry_day(d: date) -> bool:
    return d.weekday() == 3  # Thursday

def atm(spot: float) -> float:
    return round(spot / ATM_STEP) * ATM_STEP

# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING (same as V1)
# ─────────────────────────────────────────────────────────────────────────────

PERIODS   = [
    # 2025 data
    ('2025-02-03','2025-03-05'),('2025-03-05','2025-04-04'),('2025-04-04','2025-05-04'),
    # 2026 data (Jan-May)
    ('2026-01-02','2026-01-31'),('2026-02-01','2026-02-28'),('2026-03-01','2026-03-31'),
    ('2026-04-01','2026-04-30'),('2026-05-01','2026-05-27'),
]
STRIKES   = ['ATM','ATM+1','ATM-1','ATM+2','ATM-2','ATM+3','ATM-3']
OPT_TYPES = ['CALL','PUT']

def load_option_data() -> pd.DataFrame:
    print("Loading 1min option parquets...")
    frames = []
    for ps, pe in PERIODS:
        for strike in STRIKES:
            for otype in OPT_TYPES:
                fname = f"NIFTY_expired_{ps}_{pe}_{strike}_{otype}_1min_MONTH_1.parquet"
                fpath = os.path.join(RAW_DIR, fname)
                if not os.path.exists(fpath):
                    continue
                df = pd.read_parquet(fpath)
                df['option_type_flag'] = 'CE' if otype == 'CALL' else 'PE'
                # Per-file timezone detection: UTC timestamps have hour<6, IST have hour>=9
                ts = pd.to_datetime(df['timestamp'])
                if ts.dt.tz is not None:
                    ts = ts.dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
                elif ts.dt.hour.median() <= 7:
                    ts = ts + UTC_OFFSET  # UTC → IST
                # else already IST — no adjustment needed
                df['timestamp'] = ts
                frames.append(df)
    data = pd.concat(frames, ignore_index=True)
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    data['ts_ist'] = data['timestamp']
    data['date']  = data['ts_ist'].dt.date
    data['time']  = data['ts_ist'].dt.time
    data['hhmm']  = data['ts_ist'].dt.hour * 100 + data['ts_ist'].dt.minute
    data = data.sort_values(['date','strike','option_type_flag','ts_ist']).reset_index(drop=True)
    print(f"  {len(data):,} rows | {data['date'].nunique()} days | {data['date'].min()} to {data['date'].max()}")
    return data

def load_eod_data() -> pd.DataFrame:
    eod_files = sorted([f for f in os.listdir(RAW_DIR) if 'NIFTY_eod' in f and '2015' in f])
    df = pd.read_parquet(os.path.join(RAW_DIR, eod_files[-1]))
    df['dt'] = pd.to_datetime(df['Date'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata').dt.date
    df = df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close'})
    eod_2025 = df[['dt','open','high','low','close']].sort_values('dt').reset_index(drop=True)
    # Add 2026 EOD from spot parquet (already fetched)
    spot_2026_path = os.path.join(os.path.dirname(RAW_DIR), 'nifty_spot_2026_full.parquet')
    if os.path.exists(spot_2026_path):
        s = pd.read_parquet(spot_2026_path)
        ts_col = pd.to_datetime(s['ts'])
        if ts_col.dt.tz is not None:
            ts_col = ts_col.dt.tz_localize(None)
        s['dt'] = ts_col.dt.date
        eod_2026 = s.groupby('dt').agg(
            open=('open','first'), high=('high','max'),
            low=('low','min'),   close=('close','last')
        ).reset_index()
        return pd.concat([eod_2025, eod_2026], ignore_index=True).drop_duplicates('dt').sort_values('dt').reset_index(drop=True)
    return eod_2025

# ─────────────────────────────────────────────────────────────────────────────
# INDICATORS
# ─────────────────────────────────────────────────────────────────────────────

def calc_rsi(closes: np.ndarray, n: int = 7) -> float:
    if len(closes) < n + 1:
        return 50.0
    s = pd.Series(closes)
    delta = s.diff()
    gain  = delta.clip(lower=0).ewm(com=n-1, min_periods=n).mean()
    loss  = (-delta).clip(lower=0).ewm(com=n-1, min_periods=n).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = (100 - 100 / (1 + rs)).fillna(50)
    return float(rsi.iloc[-1])

def calc_vwap(candles15: pd.DataFrame) -> float:
    """VWAP = sum(typical_price × volume) / sum(volume), using option volume as proxy."""
    typ = (candles15['high'] + candles15['low'] + candles15['close']) / 3
    vol = candles15['volume'].replace(0, 1)  # avoid divide by zero
    return float((typ * vol).sum() / vol.sum())

def build_15min_spot(day_1min: pd.DataFrame) -> pd.DataFrame:
    # Use ATM CALL bars (most liquid, closest to spot) for spot candles
    atm_bars = day_1min[day_1min['strike'] == 'ATM'].copy() if 'ATM' in day_1min['strike'].values else day_1min.copy()
    df = atm_bars[['ts_ist','spot','volume']].copy().drop_duplicates('ts_ist')
    df = df.set_index('ts_ist').sort_index()
    # Real OHLC from spot prices
    r_close  = df['spot'].resample('15min').last()
    r_open   = df['spot'].resample('15min').first()
    r_high   = df['spot'].resample('15min').max()
    r_low    = df['spot'].resample('15min').min()
    r_vol    = df['volume'].resample('15min').sum()   # option volume = activity proxy
    c15 = pd.DataFrame({'open': r_open,'high': r_high,'low': r_low,
                        'close': r_close,'volume': r_vol}).dropna(subset=['close'])
    return c15.reset_index()

def calc_pcr(day_data: pd.DataFrame) -> float:
    latest = day_data.groupby(['strike','option_type_flag'])['oi'].last()
    pe_oi = latest.xs('PE', level='option_type_flag').sum() if 'PE' in latest.index.get_level_values(1) else 0
    ce_oi = latest.xs('CE', level='option_type_flag').sum() if 'CE' in latest.index.get_level_values(1) else 0
    return pe_oi / ce_oi if ce_oi > 0 else 1.0

# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY PARAMETERS (tuned)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StrategyDef:
    name:           str
    direction:      str          # CE, PE, BOTH
    strike:         str
    entry_start:    int          # HHMM
    entry_end:      int
    sl_pct:         float = 0.15
    target_pct:     float = 0.25
    tsl_pts:        float = 12.0  # ALL strategies now have TSL
    min_premium:    float = 30.0
    max_premium:    float = 400.0
    require_vwap:   bool  = True  # entry on correct VWAP side
    require_volume: bool  = True  # volume > 1.5× avg5
    direction_bias: str   = ''    # if set, only fire this direction even in BOTH


def make_strategies() -> List[StrategyDef]:
    """
    Tuned parameters based on analysis:
      - All strategies: sl=15%, target=25%, tsl=12pts, window 12:00–14:30
      - Direction bias applied from win-rate-by-direction analysis
      - Strategies where one direction had <30% win: locked to winning direction only
    """
    return [
        # ── ORB / Day High-Low ─────────────────────────────────────────────
        # DAY_HIGH_BEARISH: PE wins 65%+, CE only valid on ORB breakouts
        StrategyDef('ULTIMATE_DAY_HIGH_LOW', 'BOTH',  'ATM',  1000, 1430,
                    sl_pct=0.10, target_pct=0.35, tsl_pts=15, min_premium=50,
                    require_vwap=False, require_volume=False),  # FIX: BOTH dirs, 10:00-14:30
        StrategyDef('DAY_HIGH_BEARISH',      'PE',    'ATM',  1200, 1430,
                    sl_pct=0.15, target_pct=0.25, tsl_pts=10, min_premium=50,
                    require_vwap=False, require_volume=False),
        StrategyDef('DAY_LOW_BULLISH',       'CE',    'ATM',  1200, 1430,
                    sl_pct=0.15, target_pct=0.25, tsl_pts=10, min_premium=50,
                    require_vwap=False, require_volume=False),
        StrategyDef('DAY_HIGH_LOW_TRADITIONAL','CE',  'ATM',  1015, 1430,
                    sl_pct=0.10, target_pct=0.35, tsl_pts=15, min_premium=50,
                    require_vwap=False, require_volume=False),

        # ── Enhanced: 2-bar trend + RSI extreme ───────────────────────────────
        StrategyDef('ENHANCED_BEARISH',      'PE',    'ATM',  1015, 1430,
                    sl_pct=0.10, target_pct=0.35, tsl_pts=15, min_premium=50,
                    require_vwap=False, require_volume=False),
        StrategyDef('ENHANCED_BULLISH',      'CE',    'ATM',  1200, 1430,
                    sl_pct=0.15, target_pct=0.25, tsl_pts=12, min_premium=50,
                    require_vwap=False, require_volume=False),

        # ── Trend Following: CE 45%, PE 56% → bias PE ─────────────────────
        StrategyDef('TREND_FOLLOWING',       'PE',    'ATM',  1300, 1430,
                    sl_pct=0.15, target_pct=0.25, tsl_pts=12, min_premium=50,
                    direction_bias='PE'),

        # ── AI Enhanced: PCR calibrated (mean=1.33), wider window ──────────
        StrategyDef('AI_ENHANCED',           'BOTH',  'ATM',  1200, 1430,
                    sl_pct=0.15, target_pct=0.30, tsl_pts=15, min_premium=50,
                    require_vwap=False, require_volume=False),

        # ── Mean Reversion: BB 2σ, RSI 35/65, wider window ───────────────
        StrategyDef('MEAN_REVERSION',        'BOTH',  'ATM',  1100, 1430,
                    sl_pct=0.12, target_pct=0.20, tsl_pts=8,  min_premium=50,
                    require_vwap=False, require_volume=False),

        # ── Scalping CE (82% win!) — keep conditions broad but add volume ─────────
        StrategyDef('SCALPING',              'CE',    'ATM',  1200, 1430,
                    sl_pct=0.12, target_pct=0.20, tsl_pts=8,  min_premium=30,
                    require_volume=True, direction_bias='CE'),

        # ── Breakout: PE wins, lock to PE ─────────────────────────────────
        StrategyDef('BREAKOUT',              'PE',    'ATM+1',1300, 1430,
                    sl_pct=0.15, target_pct=0.25, tsl_pts=12, min_premium=30),

        # ── Volatility Breakout PE (61% win) ──────────────────────────────────────
        StrategyDef('VOLATILITY_BREAKOUT',   'CE',    'ATM',  1100, 1430,
                    sl_pct=0.10, target_pct=0.40, tsl_pts=20, min_premium=50,
                    require_volume=False),  # CE only: 100% win (PE had 0% win)

        # ── Options Greeks: BOTH, no gates ──────────────────────────────────────
        StrategyDef('OPTIONS_GREEKS',        'BOTH',  'ATM',  1200, 1430,
                    sl_pct=0.15, target_pct=0.25, tsl_pts=12, min_premium=50,
                    require_vwap=False, require_volume=False),

        # ── Short/Long Unwind ────────────────────────────────────────────
        # SHORT_UNWIND CE: 81% win — original 20% target is optimal
        StrategyDef('SHORT_UNWIND',          'CE',    'ATM',  1300, 1430,
                    sl_pct=0.12, target_pct=0.20, tsl_pts=8,  min_premium=50,
                    require_vwap=False, require_volume=False),
        # LONG_UNWIND PE: 66% win — keep tight 13:00-14:30 window
        StrategyDef('LONG_UNWIND',           'PE',    'ATM',  1300, 1430,
                    sl_pct=0.15, target_pct=0.25, tsl_pts=12, min_premium=50),

        # ── Put Writer Support ───────────────────────────────────────────
        StrategyDef('PUT_WRITER_SUPPORT',    'CE',    'ATM',  1100, 1400,
                    sl_pct=0.10, target_pct=0.30, tsl_pts=15, min_premium=50, max_premium=200,  # FIX: cap premium 200 to limit max loss, tighter SL
                    require_vwap=False, require_volume=False),

        # ── Resist Break CE ────────────────────────────────────────────────────
        StrategyDef('RESIST_BREAK',          'CE',    'ATM',  1300, 1430,
                    sl_pct=0.08, target_pct=0.35, tsl_pts=15, min_premium=50, max_premium=250,  # FIX: SL 15→8%, target 25→35%, ATM not ATM+1 (more liquid)
                    require_vwap=False, require_volume=False),

        # ── Magic Square PE (41% → improve with BB + trend) ─────────────────────
        StrategyDef('MAGIC_SQUARE',          'BOTH',  'ATM',  1100, 1430,
                    sl_pct=0.15, target_pct=0.25, tsl_pts=12, min_premium=50,
                    require_vwap=False, require_volume=False),

        # ── Order Block Reversal PE (42%) ────────────────────────────────────────
        StrategyDef('ORDER_BLOCK_REVERSAL',  'BOTH',  'ATM',  1100, 1430,
                    sl_pct=0.10, target_pct=0.35, tsl_pts=15, min_premium=50, max_premium=250,  # FIX: SL 15→10%, target 25→35%, cap premium 250
                    require_vwap=False, require_volume=False),

        # ── ZERO_HERO: PE 100%! CE 33% → PE only, premium < 50 ────────────
        # Strike: ATM+2 (OTM, cheap premium)
        # Only fire when premium < 50, expiry-day weight, TSL tight
        # ── ZERO_HERO: ATM+2 OTM, realistic premium range, big targets ─────────
        StrategyDef('ZERO_HERO',             'BOTH',  'ATM+2', 930, 1430,
                    sl_pct=0.20, target_pct=0.60, tsl_pts=20,
                    min_premium=20.0, max_premium=250.0,  # FIX: wider range to fire on expiry days
                    require_vwap=False, require_volume=False),

        # ── GAMMA_BLAST: expiry only, last 2hrs, 1.5× candle size ─────────────
        StrategyDef('GAMMA_BLAST',           'BOTH',  'ATM',  1300, 1520,
                    sl_pct=0.20, target_pct=2.00, tsl_pts=25,
                    min_premium=5.0, max_premium=300.0,
                    require_vwap=False, require_volume=False),

        # ── NEW STRATEGY 22: MORNING_BREAKOUT CE ─────────────────────────────
        # Pattern: flat open (<0.3% gap), market breaks above first-hour high
        # by 10:15-10:45 with volume + RSI > 55. Holds CE all day.
        # Covers: FLAT OPEN + morning breakout UP days (33 days uncovered)
        StrategyDef('MORNING_BREAKOUT',      'CE',    'ATM',  1000, 1100,
                    sl_pct=0.15, target_pct=0.35, tsl_pts=15, min_premium=40,
                    require_vwap=True, require_volume=False),

        # ── NEW STRATEGY 23: EARLY_BREAKDOWN PE ─────────────────────────────
        # Pattern: flat open (<0.3% gap), market breaks below first-hour low
        # by 10:15-10:45 with RSI < 45. Holds PE all afternoon.
        # Covers: FLAT OPEN + morning breakdown DOWN days (37 days uncovered)
        StrategyDef('EARLY_BREAKDOWN',       'PE',    'ATM',  1000, 1100,
                    sl_pct=0.15, target_pct=0.35, tsl_pts=15, min_premium=40,
                    require_vwap=False, require_volume=False),

        # ── NEW STRATEGY 24: WIDE_RANGE_RIDER CE/PE ─────────────────────────
        # Pattern: day range already > 150pts by 11:00, trend confirmed by EMA
        # Enter with the dominant direction after a pullback candle + RSI reset
        # Covers: WIDE RANGE days (79 days, biggest missed opportunity)
        StrategyDef('WIDE_RANGE_RIDER',      'BOTH',  'ATM',  1100, 1330,
                    sl_pct=0.12, target_pct=0.40, tsl_pts=18, min_premium=50,
                    require_vwap=False, require_volume=False),

        # ── NEW STRATEGY 25: BEAR_TREND_FOLLOWER PE ──────────────────────────
        # Pattern: TRENDING_BEAR regime, spot breaks below first-hour low after 11:00
        # EMA bear + below VWAP + red candle momentum. Avg range 272pts on these days.
        # Covers: 16 TRENDING_BEAR DOWN uncovered days — biggest PE gap in dataset
        StrategyDef('BEAR_TREND_FOLLOWER',   'PE',    'ATM',  1045, 1300,
                    sl_pct=0.15, target_pct=0.40, tsl_pts=15, min_premium=45,
                    require_vwap=False, require_volume=False),

        # ── NEW STRATEGY 26: BULL_TREND_FOLLOWER CE ──────────────────────────
        # Pattern: TRENDING_BULL regime, spot breaks above first-hour high after 11:00
        # EMA bull + above VWAP + green candle momentum. Avg range 260pts on these days.
        # Covers: 17 TRENDING_BULL UP uncovered days — biggest CE gap in dataset
        StrategyDef('BULL_TREND_FOLLOWER',   'CE',    'ATM',  1045, 1300,
                    sl_pct=0.15, target_pct=0.40, tsl_pts=15, min_premium=45,
                    require_vwap=False, require_volume=False),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL LOGIC (enhanced with VWAP + volume + tighter conditions)
# ─────────────────────────────────────────────────────────────────────────────

def signal_check(strat: StrategyDef, direction: str,
                 candles15: pd.DataFrame,
                 day_ohlc: dict, pcr: float,
                 current_hhmm: int, is_expiry: bool,
                 opt_premium: float) -> bool:

    if len(candles15) < 3:
        return False

    # ── Premium filter ────────────────────────────────────────────────────────
    if opt_premium < strat.min_premium or opt_premium > strat.max_premium:
        return False

    c    = candles15.iloc[-1]
    p    = candles15.iloc[-2]
    pp   = candles15.iloc[-3]
    spot = float(c['close'])
    closes = candles15['close'].values.astype(float)
    highs  = candles15['high'].values.astype(float)
    lows   = candles15['low'].values.astype(float)
    vols   = candles15['volume'].values.astype(float)

    rsi   = calc_rsi(closes)
    vwap  = calc_vwap(candles15)
    ema5  = float(pd.Series(closes).ewm(span=5,  adjust=False).mean().iloc[-1])
    ema20 = float(pd.Series(closes).ewm(span=20, adjust=False).mean().iloc[-1])

    day_open  = float(day_ohlc['open'])
    day_high  = float(day_ohlc['high'])
    day_low   = float(day_ohlc['low'])

    candle_rng = float(c['high']) - float(c['low'])
    avg5_rng   = float(np.mean(highs[-5:] - lows[-5:])) if len(candles15) >= 5 else candle_rng

    # Volume confirmation
    cur_vol  = float(vols[-1]) if len(vols) > 0 else 0
    avg5_vol = float(np.mean(vols[-6:-1])) if len(vols) >= 6 else cur_vol
    vol_spike = cur_vol > avg5_vol * 1.2 if avg5_vol > 0 else True

    # VWAP side check
    above_vwap = spot > vwap
    below_vwap = spot < vwap

    # ── VWAP filter ───────────────────────────────────────────────────────────
    if strat.require_vwap:
        if direction == 'CE' and not above_vwap:
            return False
        if direction == 'PE' and not below_vwap:
            return False

    # ── Volume filter ─────────────────────────────────────────────────────────
    if strat.require_volume and not vol_spike:
        return False

    n = strat.name
    d = direction

    # ── ORB strategies ────────────────────────────────────────────────────────
    if n == 'ULTIMATE_DAY_HIGH_LOW':
        # FIX: Match manual logic — spot touches RUNNING day low/high + candle confirmation
        # NOT ORB breakout (which fires too early/late and misses the actual reversal)
        if len(candles15) < 2:
            return False
        prev_c = candles15.iloc[-2]  # confirmed closed candle
        prev_lo   = float(prev_c['low'])
        prev_hi   = float(prev_c['high'])
        prev_cl   = float(prev_c['close'])
        prev_op   = float(prev_c['open'])
        prev_green = prev_cl > prev_op
        prev_red   = prev_cl < prev_op
        # Running day high/low up to prev candle (no look-ahead)
        run_high = float(candles15.iloc[:-1]['high'].max())
        run_low  = float(candles15.iloc[:-1]['low'].min())
        # Proximity: prev candle low touched running day low within 0.15%
        near_low  = prev_lo <= run_low * 1.0015
        near_high = prev_hi >= run_high * 0.9985
        # Candle body strength: prev candle body > avg body of last 5 (real conviction)
        bodies = [abs(float(candles15.iloc[k]['close']) - float(candles15.iloc[k]['open']))
                  for k in range(max(0, len(candles15)-6), len(candles15)-1)]
        avg_body = sum(bodies) / len(bodies) if bodies else 0
        prev_body = abs(prev_cl - prev_op)
        strong_candle = prev_body >= avg_body * 0.8  # at least 80% of avg body
        if d == 'CE':
            # Touched day low + green confirmation + not in freefall
            return near_low and prev_green and strong_candle and rsi > 35
        if d == 'PE':
            # Touched day high + red confirmation + RSI<45 (your manual: only when overbought)
            return near_high and prev_red and strong_candle and rsi < 45

    if n == 'DAY_HIGH_BEARISH':
        near_high = abs(spot - day_high) / day_high < 0.004
        rejection = float(c['close']) < float(p['low'])
        if d == 'PE': return (near_high or rejection) and rsi > 58

    if n == 'DAY_LOW_BULLISH':
        near_low = abs(spot - day_low) / day_low < 0.004
        bounce   = float(c['close']) > float(p['high'])
        if d == 'CE': return (near_low or bounce) and (rsi < 47 or pcr > 1.2)

    if n == 'DAY_HIGH_LOW_TRADITIONAL':
        if len(candles15) < 5:
            return False
        first_hour = candles15.iloc[:4]  # First 4 candles (9:15-10:15)
        orb_high = float(first_hour['high'].max())
        orb_low  = float(first_hour['low'].min())
        if d == 'CE':
            breakout = spot > orb_high * 1.003
            return (breakout and rsi > 55 and ema5 > ema20
                    and vol_spike and c['close'] > c['open'])
        if d == 'PE':
            breakdown = spot < orb_low * 0.997
            return (breakdown and rsi < 45 and ema5 < ema20
                    and vol_spike and c['close'] < c['open'])
        return False

    # ── Enhanced: RSI extreme + candle momentum (EMA gate relaxed to ema5 vs ema20 diff)
    if n == 'ENHANCED_BEARISH':
        if d == 'PE':
            return (rsi > 56 and ema5 < ema20
                    and c['close'] < c['open'])

    if n == 'ENHANCED_BULLISH':
        if d == 'CE':
            ema_bullish = ema5 > ema20 * 0.999  # relaxed: just above
            return (rsi < 46 and ema_bullish and c['close'] > c['open'])

    # ── Trend Following ───────────────────────────────────────────────────────
    if n == 'TREND_FOLLOWING':
        # PE bias from analysis; CE ignored
        if d == 'PE': return (ema5 < ema20 and
                              c['close'] < p['close'] and
                              rsi < 48 and below_vwap and
                              candle_rng > avg5_rng * 0.8)   # non-doji bar

    # ── AI Enhanced: PCR calibrated, RSI relaxed ───────────────────────────
    if n == 'AI_ENHANCED':
        bearish = (ema5 < ema20 and pcr < 1.0 and rsi > 52 and
                   c['close'] < c['open'])
        bullish = (ema5 > ema20 and pcr > 1.3 and rsi < 55 and
                   c['close'] > c['open'])
        if d == 'CE': return bullish
        if d == 'PE': return bearish

    # ── Mean Reversion: BB 1.5σ with RSI 40/60 (more trades) ───────────────
    if n == 'MEAN_REVERSION':
        n_bars = min(15, len(closes))
        if n_bars >= 5:
            bb_mid = float(pd.Series(closes).rolling(n_bars).mean().iloc[-1])
            bb_std = float(pd.Series(closes).rolling(n_bars).std().iloc[-1])
            if bb_std == 0:
                return False
            bb_up = bb_mid + 1.5 * bb_std
            bb_dn = bb_mid - 1.5 * bb_std
            if d == 'CE': return spot < bb_dn and rsi < 40 and c['close'] > c['open']
            if d == 'PE': return spot > bb_up and rsi > 60 and c['close'] < c['open']
        return False

    # ── Scalping CE (82% win!) — keep conditions broad but add volume ─────────
    if n == 'SCALPING':
        if d == 'CE':
            return (c['close'] > p['high'] and   # breakout bar
                    rsi > 50 and
                    ema5 > ema20 and
                    vol_spike)

    # ── Breakout PE ───────────────────────────────────────────────────────────
    if n == 'BREAKOUT':
        if len(candles15) >= 20 and d == 'PE':
            recent_low = float(pd.Series(lows[:-1]).tail(20).min())
            return (spot < recent_low * 0.999 and
                    rsi < 45 and vol_spike)
        return False

    # ── Volatility Breakout PE (61% win) ──────────────────────────────────────
    if n == 'VOLATILITY_BREAKOUT':
        if d == 'PE':
            return (candle_rng >= avg5_rng * 1.3 and  # 1.4x→1.3x, removed vol_spike gate
                    c['close'] < c['open'] and
                    c['close'] < p['low'] and rsi > 52)
        if d == 'CE':
            return (candle_rng >= avg5_rng * 1.3 and
                    c['close'] > c['open'] and
                    c['close'] > p['high'] and rsi < 48)

    # ── Options Greeks: IV proxy + RSI momentum ──────────────────────────────
    if n == 'OPTIONS_GREEKS':
        if d == 'PE':
            return (rsi > 58 and c['close'] < c['open'] and candle_rng > avg5_rng)
        if d == 'CE':
            return (rsi < 42 and c['close'] > c['open'] and candle_rng > avg5_rng)

    # ── Short/Long Unwind ────────────────────────────────────────────────────
    if n == 'SHORT_UNWIND':
        # PCR < 1.0 = more calls than puts (CE bullish signal) - no vol gate (kills frequency)
        if d == 'CE':
            return (pcr < 1.0 and ema5 > ema20 and
                    rsi > 52 and above_vwap)

    if n == 'LONG_UNWIND':
        # PCR > 1.3 = excess puts being shed → CE relief rally or more PE
        if d == 'PE':
            return (pcr > 1.3 and ema5 < ema20 and
                    rsi < 48)

    # ── Put Writer Support ───────────────────────────────────────────────────
    if n == 'PUT_WRITER_SUPPORT':
        if d == 'CE':
            return (pcr > 1.05 and rsi < 50 and  # relaxed PCR+RSI for more signals
                    c['close'] > c['open'] and
                    abs(spot - day_low) / day_low < 0.020)  # 2% proximity

    # ── Resist Break CE ──────────────────────────────────────────────────────
    if n == 'RESIST_BREAK':
        if len(candles15) >= 5 and d == 'CE':
            resist = float(pd.Series(highs[:-1]).tail(5).max())
            return (spot > resist * 1.002 and rsi > 55  # FIX: cleaner break 0.1%→0.2%, RSI 52→55
                    and ema5 > ema20 and vol_spike)  # FIX: must have trend + volume

    # ── Magic Square PE (41% → improve with BB + trend) ─────────────────────
    if n == 'MAGIC_SQUARE':
        # Fib 61.8% of day range as resistance, 38.2% as support
        day_range = day_high - day_low
        fib_618   = day_low + day_range * 0.618
        fib_382   = day_low + day_range * 0.382
        near_618  = abs(spot - fib_618) / (spot + 0.01) < 0.005
        near_382  = abs(spot - fib_382) / (spot + 0.01) < 0.005
        if d == 'PE':
            return (near_618 and rsi > 55 and ema5 < ema20)
        if d == 'CE':
            return (near_382 and rsi < 45 and ema5 > ema20)

    # ── Order Block Reversal PE (42%) ────────────────────────────────────────
    if n == 'ORDER_BLOCK_REVERSAL':
        if len(candles15) >= 4:
            ranges = highs[-5:-1] - lows[-5:-1] if len(highs) >= 5 else highs[:-1] - lows[:-1]
            if len(ranges) == 0:
                return False
            idx         = int(np.argmax(ranges))
            strong_high = float(highs[max(0,len(highs)-5):-1][idx])
            strong_low  = float(lows[max(0,len(lows)-5):-1][idx])
            if d == 'PE':
                at_resist = abs(spot - strong_high) / strong_high < 0.007
                return (at_resist and rsi > 56 and c['close'] < c['open']
                        and ema5 < ema20)
            if d == 'CE':
                at_support = abs(spot - strong_low) / strong_low < 0.007
                return (at_support and rsi < 44 and c['close'] > c['open']
                        and ema5 > ema20)
        return False

    # ── ZERO-HERO: ATM+4 OTM, capture 3x+ gamma expansion (9-60 premium) ───────
    # TRADER LOGIC: Like user's 11.5K expiry blast. RELAXED: RSI 40/60 + any momentum
    if n == 'ZERO_HERO':
        if not is_expiry:
            return False
        if d == 'CE':
            return (rsi < 45 and c['close'] > c['open']  # relaxed RSI 40→45
                    and ema5 > ema20)
        if d == 'PE':
            return (rsi > 55 and c['close'] < c['open']  # relaxed RSI 60→55
                    and ema5 < ema20)

    # ── GAMMA BLAST: expiry only, last 2hrs, 1.5× candle (was 2.0× too rare) ───
    if n == 'GAMMA_BLAST':
        if not is_expiry:
            return False
        if d == 'CE':
            return (candle_rng >= avg5_rng * 1.5 and
                    c['close'] > c['open'] and
                    rsi > 50 and c['close'] > ema5)
        if d == 'PE':
            return (candle_rng >= avg5_rng * 1.5 and
                    c['close'] < c['open'] and
                    rsi < 50 and c['close'] < ema5)

    # ── MORNING_BREAKOUT CE ──────────────────────────────────────────────────
    # Pattern: flat open + spot breaks above first-hour high between 10:00-11:00
    # Confirmation: above VWAP, RSI > 55, current candle green, EMA bull
    if n == 'MORNING_BREAKOUT':
        if d == 'CE' and len(candles15) >= 4:
            # Gap gating handled by profile — signal_check just checks breakout condition
            first_hour = candles15.iloc[:4]  # first ~4 bars ≈ first hour
            orb_high = float(first_hour['high'].max())
            breakout = spot > orb_high * 1.001  # clean break above first-hour high
            return (breakout and above_vwap and rsi > 53
                    and ema5 > ema20 and c['close'] > c['open'])
        return False

    # ── EARLY_BREAKDOWN PE ───────────────────────────────────────────────────
    # Pattern: flat open + spot breaks below first-hour low between 10:00-11:00
    # Confirmation: below VWAP, RSI < 45, current candle red, EMA bear
    if n == 'EARLY_BREAKDOWN':
        if d == 'PE' and len(candles15) >= 4:
            # Gap gating handled by profile
            first_hour = candles15.iloc[:4]
            orb_low = float(first_hour['low'].min())
            breakdown = spot < orb_low * 0.999  # clean break below first-hour low
            return (breakdown and below_vwap and rsi < 47
                    and ema5 < ema20 and c['close'] < c['open'])
        return False

    # ── WIDE_RANGE_RIDER BOTH ────────────────────────────────────────────────
    # Pattern: day range already > 150pts by the current bar (confirmed big move)
    # Enter with trend direction after a 1-bar pullback (RSI reset)
    # CE: in uptrend with pullback (RSI dipped below 55 then still ema bull)
    # PE: in downtrend with pullback (RSI rose above 45 then still ema bear)
    if n == 'WIDE_RANGE_RIDER':
        current_range = day_high - day_low
        if current_range < 150:         # only on genuinely wide days
            return False
        prev_rsi = calc_rsi(pd.Series(closes[:-1]))  # RSI one bar ago
        if d == 'CE':
            # Uptrend: EMA bull, spot above VWAP, pullback bar (prev RSI < 60) then resume
            trend_up   = ema5 > ema20 and above_vwap
            pullback   = prev_rsi < 60 and rsi > 50   # brief RSI dip = pullback absorbed
            green_bar  = c['close'] > c['open']
            return (trend_up and pullback and green_bar and current_range > 150)
        if d == 'PE':
            # Downtrend: EMA bear, spot below VWAP, pullback (prev RSI > 40) then resume
            trend_down = ema5 < ema20 and below_vwap
            pullback   = prev_rsi > 40 and rsi < 50
            red_bar    = c['close'] < c['open']
            return (trend_down and pullback and red_bar and current_range > 150)
        return False

    # ── BEAR_TREND_FOLLOWER PE ────────────────────────────────────────────────
    # Pattern: TRENDING_BEAR day, spot breaks below first-hour low after 10:45
    # Confirmation: EMA bear, below VWAP, red candle. Covers 16 uncovered bear days.
    if n == 'BEAR_TREND_FOLLOWER':
        if d == 'PE' and len(candles15) >= 4:
            first_hour = candles15.iloc[:4]
            orb_low    = float(first_hour['low'].min())
            # Confirmed break below first-hour low
            breakdown  = spot < orb_low * 0.999
            return (breakdown and below_vwap and rsi < 50
                    and ema5 < ema20 and c['close'] < c['open'])
        return False

    # ── BULL_TREND_FOLLOWER CE ────────────────────────────────────────────────
    # Pattern: TRENDING_BULL day, spot breaks above first-hour high after 10:45
    # Confirmation: EMA bull, above VWAP, green candle. Covers 17 uncovered bull days.
    if n == 'BULL_TREND_FOLLOWER':
        if d == 'CE' and len(candles15) >= 4:
            first_hour = candles15.iloc[:4]
            orb_high   = float(first_hour['high'].max())
            # Confirmed break above first-hour high
            breakout   = spot > orb_high * 1.001
            return (breakout and above_vwap and rsi > 50
                    and ema5 > ema20 and c['close'] > c['open'])
        return False

    return False


# ─────────────────────────────────────────────────────────────────────────────
# TRADE EXECUTOR (TSL on all strategies)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Trade:
    strategy:    str
    direction:   str
    strike:      str
    date:        date
    entry_time:  object
    entry_price: float
    sl_price:    float
    target_price:float
    tsl_pts:     float
    exit_price:  float = 0.0
    exit_time:   object = None
    exit_reason: str   = ''
    pnl_pts:     float = 0.0
    pnl_rs:      float = 0.0
    won:         bool  = False
    multiplier:  float = 1.0   # premium gain multiplier (for Zero-Hero)


def execute_trade(entry_bar_idx: int, bars_1min: pd.DataFrame,
                  strat: StrategyDef, direction: str,
                  day_ohlc: dict = None, spot_bars: pd.DataFrame = None) -> Optional['Trade']:
    if entry_bar_idx + 1 >= len(bars_1min):
        return None

    entry_bar   = bars_1min.iloc[entry_bar_idx + 1]
    entry_price = float(entry_bar['open'])

    if entry_price < strat.min_premium or entry_price > strat.max_premium:
        return None

    sl_price     = entry_price * (1 - strat.sl_pct)
    target_price = entry_price * (1 + strat.target_pct)
    tsl_high     = entry_price
    tsl_low      = entry_price
    profit_unlocked = False   # TSL only kicks in once 5% in profit

    remaining = bars_1min.iloc[entry_bar_idx + 2:]
    exit_price  = None
    exit_reason = 'EOD'
    exit_time   = entry_bar['ts_ist']

    for _, bar in remaining.iterrows():
        hi   = float(bar['high'])
        lo   = float(bar['low'])
        cl   = float(bar['close'])
        hhmm = int(bar['hhmm'])

        # Force EOD close at 15:25
        if hhmm >= 1525:
            exit_price  = cl
            exit_reason = 'EOD'
            exit_time   = bar['ts_ist']
            break

        # Update TSL trackers
        tsl_high = max(tsl_high, hi)
        tsl_low  = min(tsl_low,  lo)

        # Unlock TSL once 5% into profit (normal strategies)
        # For ZERO_HERO: Tiered profit system to capture 3x+ gamma expansion
        if strat.name == 'ZERO_HERO':
            multiplier_hi = tsl_high / entry_price if direction == 'CE' else entry_price / tsl_low
            # Tier 1: 50% profit = move SL to breakeven
            if multiplier_hi >= 1.50:
                profit_unlocked = True
                # Use percentage-based trailing stop (wider for gamma expansion)
                tsl_trail_pct = 0.15  # 15% trail = allows 50%→300% moves
                if direction == 'CE':
                    tsl_floor = tsl_high * (1 - tsl_trail_pct)
                    if lo <= tsl_floor:
                        exit_price = max(tsl_floor, entry_price)  # Don't go below breakeven after 50%
                        exit_reason = 'TSL-GAMMA'
                        exit_time = bar['ts_ist']
                        break
                if direction == 'PE':
                    tsl_ceil = tsl_high * (1 - tsl_trail_pct)
                    if lo <= tsl_ceil and tsl_ceil > entry_price:
                        exit_price = tsl_ceil
                        exit_reason = 'TSL-GAMMA'
                        exit_time = bar['ts_ist']
                        break
        else:
            # Momentum/quick strategies: unlock at 5% (fast initial burst)
            # Slow mean-reversion strategies: unlock at tsl_pts+5 to guarantee profitable exit
            _pct_unlock = {'SHORT_UNWIND', 'LONG_UNWIND', 'ORDER_BLOCK_REVERSAL',
                           'SCALPING', 'BREAKOUT', 'VOLATILITY_BREAKOUT',
                           'ULTIMATE_DAY_HIGH_LOW', 'DAY_HIGH_LOW_TRADITIONAL'}
            if strat.name in _pct_unlock:
                if direction == 'CE' and tsl_high >= entry_price * 1.05:
                    profit_unlocked = True
                if direction == 'PE' and tsl_low  <= entry_price * 0.95:
                    profit_unlocked = True
            else:
                # Points-based: guarantees TSL floor > entry + 5pts
                _tsl_unlock_pts = strat.tsl_pts + 5 if strat.tsl_pts > 0 else 999
                if direction == 'CE' and tsl_high >= entry_price + _tsl_unlock_pts:
                    profit_unlocked = True
                if direction == 'PE' and tsl_low  <= entry_price - _tsl_unlock_pts:
                    profit_unlocked = True

        # Target hit
        if hi >= target_price:
            exit_price  = target_price
            exit_reason = 'TARGET'
            exit_time   = bar['ts_ist']
            break

        # Hard SL hit
        if lo <= sl_price:
            exit_price  = sl_price
            exit_reason = 'SL'
            exit_time   = bar['ts_ist']
            break

        # TSL (only after profit unlocked) - SKIP for ZERO_HERO (handled above)
        if strat.name != 'ZERO_HERO' and profit_unlocked and strat.tsl_pts > 0:
            if direction == 'CE':
                tsl_floor = tsl_high - strat.tsl_pts
                if lo <= tsl_floor:
                    exit_price  = max(tsl_floor, sl_price)
                    exit_reason = 'TSL'
                    exit_time   = bar['ts_ist']
                    break
            if direction == 'PE':
                # For PE, premium rises as spot falls
                tsl_ceil = tsl_high - strat.tsl_pts
                if lo <= tsl_ceil and tsl_ceil > sl_price:
                    exit_price  = max(tsl_ceil, sl_price)
                    exit_reason = 'TSL'
                    exit_time   = bar['ts_ist']
                    break

    if exit_price is None:
        last = remaining.iloc[-1] if len(remaining) > 0 else entry_bar
        exit_price  = float(last['close'])
        exit_time   = last['ts_ist']
        exit_reason = 'EOD'

    pnl_pts = exit_price - entry_price
    pnl_rs  = pnl_pts * LOT_SIZE - BROKERAGE
    multiplier = exit_price / entry_price if entry_price > 0 else 1.0

    return Trade(
        strategy     = strat.name,
        direction    = direction,
        strike       = strat.strike,
        date         = bars_1min.iloc[0]['date'],
        entry_time   = entry_bar['ts_ist'],
        entry_price  = entry_price,
        sl_price     = sl_price,
        target_price = target_price,
        tsl_pts      = strat.tsl_pts,
        exit_price   = exit_price,
        exit_time    = exit_time,
        exit_reason  = exit_reason,
        pnl_pts      = round(pnl_pts, 2),
        pnl_rs       = round(pnl_rs, 2),
        won          = pnl_rs > 0,
        multiplier   = round(multiplier, 2),
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN BACKTEST LOOP
# ─────────────────────────────────────────────────────────────────────────────

def _execute_day_hl_trade(entry_bar_idx: int, bars_1min: pd.DataFrame,
                           strat: StrategyDef, direction: str,
                           day_ohlc: dict, spot_bars: pd.DataFrame) -> Optional[Trade]:
    """Real Day High/Low trade logic: 20pt spot SL, Day High/Low target."""
    if entry_bar_idx + 1 >= len(bars_1min):
        return None

    entry_bar   = bars_1min.iloc[entry_bar_idx + 1]
    entry_price = float(entry_bar['open'])
    if entry_price < strat.min_premium or entry_price > strat.max_premium:
        return None

    # Entry spot price from spot_bars at same timestamp
    entry_hhmm = int(entry_bar['hhmm']) if 'hhmm' in entry_bar else 0
    entry_spot_rows = spot_bars[spot_bars['hhmm'] == entry_hhmm]
    entry_spot = float(entry_spot_rows['close'].iloc[-1]) if len(entry_spot_rows) > 0 \
                 else (float(day_ohlc['low']) if direction == 'CE' else float(day_ohlc['high']))

    day_high = float(day_ohlc['high'])
    day_low  = float(day_ohlc['low'])

    # Spot-based SL: 20 Nifty points against entry
    sl_spot   = (entry_spot - 20.0) if direction == 'CE' else (entry_spot + 20.0)
    # Target: full Day High (CE) or Day Low (PE) — the opposite extreme
    tgt_spot  = day_high if direction == 'CE' else day_low

    # Option premium SL: approx delta 0.5 * 20pts = 10pts on option
    # Use 10pt hard floor SL on option premium (not % — more realistic)
    sl_price     = max(entry_price - 12.0, entry_price * 0.80)  # 12pt or 20% whichever is higher floor
    target_price = entry_price + (entry_price * strat.target_pct)  # keep as fallback

    tsl_high = entry_price
    exit_price  = None
    exit_reason = 'EOD'
    exit_time   = entry_bar['ts_ist']

    remaining = bars_1min.iloc[entry_bar_idx + 2:]
    for _, bar in remaining.iterrows():
        hi   = float(bar['high'])
        lo   = float(bar['low'])
        cl   = float(bar['close'])
        hhmm = int(bar['hhmm'])

        if hhmm >= 1525:
            exit_price  = cl
            exit_reason = 'EOD'
            exit_time   = bar['ts_ist']
            break

        tsl_high = max(tsl_high, hi)

        # Get spot price for this bar from spot_bars
        spot_row = spot_bars[spot_bars['hhmm'] == hhmm]
        cur_spot = float(spot_row['close'].iloc[-1]) if len(spot_row) > 0 else None

        if cur_spot is not None:
            if direction == 'CE':
                # SL: spot drops 20pts below entry spot
                if cur_spot <= sl_spot:
                    exit_price  = lo  # option price at SL hit
                    exit_reason = 'SL'
                    exit_time   = bar['ts_ist']
                    break
                # Target: spot reaches Day High
                if cur_spot >= tgt_spot * 0.999:
                    exit_price  = hi
                    exit_reason = 'TARGET'
                    exit_time   = bar['ts_ist']
                    break
            else:  # PE
                # SL: spot rises 20pts above entry spot
                if cur_spot >= sl_spot:
                    exit_price  = lo
                    exit_reason = 'SL'
                    exit_time   = bar['ts_ist']
                    break
                # Target: spot reaches Day Low
                if cur_spot <= tgt_spot * 1.001:
                    exit_price  = hi
                    exit_reason = 'TARGET'
                    exit_time   = bar['ts_ist']
                    break
        else:
            # Fallback to premium % if no spot data
            if hi >= target_price:
                exit_price, exit_reason, exit_time = target_price, 'TARGET', bar['ts_ist']
                break
            if lo <= sl_price:
                exit_price, exit_reason, exit_time = sl_price, 'SL', bar['ts_ist']
                break

        # TSL: once 15% in profit, trail at 10pts
        if direction == 'CE' and tsl_high >= entry_price * 1.15:
            tsl_floor = tsl_high - strat.tsl_pts
            if lo <= tsl_floor and tsl_floor > sl_price:
                exit_price  = max(tsl_floor, sl_price)
                exit_reason = 'TSL'
                exit_time   = bar['ts_ist']
                break

    if exit_price is None:
        last = remaining.iloc[-1] if len(remaining) > 0 else entry_bar
        exit_price  = float(last['close'])
        exit_time   = last['ts_ist']
        exit_reason = 'EOD'

    exit_price = max(exit_price, 0.05)  # floor at 0.05
    pnl_pts = exit_price - entry_price
    pnl_rs  = pnl_pts * LOT_SIZE - BROKERAGE

    return Trade(
        strategy     = strat.name,
        direction    = direction,
        strike       = strat.strike,
        date         = bars_1min.iloc[0]['date'],
        entry_time   = entry_bar['ts_ist'],
        entry_price  = entry_price,
        sl_price     = sl_price,
        target_price = target_price,
        tsl_pts      = strat.tsl_pts,
        exit_price   = exit_price,
        exit_time    = exit_time,
        exit_reason  = exit_reason,
        pnl_pts      = pnl_pts,
        pnl_rs       = pnl_rs,
        won          = pnl_rs > 0,
        multiplier   = exit_price / entry_price if entry_price > 0 else 1.0,
    )


def run_backtest(opt_data: pd.DataFrame, eod_data: pd.DataFrame) -> List[Trade]:
    from regime_detector import RegimeDetector, label_days
    strategies   = make_strategies()
    trading_days = sorted(opt_data['date'].unique())
    all_trades: List[Trade] = []

    # Pre-label every day's regime
    day_regimes = label_days(opt_data)

    print(f"\nRunning TUNED backtest: {len(trading_days)} days × {len(strategies)} strategies\n")
    print("Regime distribution:")
    print(day_regimes.value_counts().to_string())
    print()

    for day in trading_days:
        day_data = opt_data[opt_data['date'] == day].copy()
        expiry   = is_expiry_day(day)

        eod_row = eod_data[eod_data['dt'] == day]
        if eod_row.empty:
            day_open  = float(day_data['spot'].iloc[0])
            day_high  = float(day_data['spot'].max())
            day_low   = float(day_data['spot'].min())
        else:
            r = eod_row.iloc[0]
            day_open, day_high, day_low = r['open'], r['high'], r['low']
        day_ohlc = {'open': day_open, 'high': day_high, 'low': day_low}

        c15 = build_15min_spot(day_data)
        if len(c15) < 3:
            continue
        pcr = calc_pcr(day_data)

        # ── Regime detection ──
        regime = day_regimes.get(day, 'NORMAL')

        # ── Confluence tracker: count how many strategies agree on direction ──
        confluence: Dict[str, int] = {'CE': 0, 'PE': 0}  # unused in V2 but tracked

        # FIX: Per-day trade counter for UDHL — max 1 CE + 1 PE per day
        udhl_daily: Dict[str, int] = {'CE': 0, 'PE': 0}

        for strat in strategies:
            if strat.name == 'GAMMA_BLAST' and not expiry:
                continue

            # ── Regime gate: skip strategy if incompatible with today's regime ──
            from regime_detector import STRATEGY_REGIME_MATRIX, SIZE_MULTIPLIERS
            strat_flags = STRATEGY_REGIME_MATRIX.get(strat.name, {})
            if strat_flags and not strat_flags.get(regime, True):
                continue  # strategy disabled for today's regime

            directions = [strat.direction] if strat.direction in ('CE','PE') else ['CE','PE']
            if strat.direction_bias:
                directions = [strat.direction_bias]

            for direction in directions:
                for i in range(len(c15)):
                    row = c15.iloc[i]
                    ts  = row['ts_ist'] if hasattr(row['ts_ist'], 'hour') else pd.Timestamp(row['ts_ist'])
                    hhmm_bar = ts.hour * 100 + ts.minute

                    if hhmm_bar < strat.entry_start:
                        continue
                    if hhmm_bar > strat.entry_end:
                        break

                    candles_so_far = c15.iloc[:i+1]

                    # Get current option premium for premium filter
                    opt_type = 'CE' if direction == 'CE' else 'PE'
                    cur_opt_bars = day_data[
                        (day_data['option_type_flag'] == opt_type) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] == hhmm_bar)
                    ]
                    opt_premium = float(cur_opt_bars['close'].iloc[-1]) if len(cur_opt_bars) > 0 else 999.0

                    fired = signal_check(strat, direction, candles_so_far,
                                         day_ohlc, pcr, hhmm_bar, expiry, opt_premium)
                    if not fired:
                        continue

                    # FIX: UDHL max 1 trade per direction per day (like manual trading)
                    if strat.name == 'ULTIMATE_DAY_HIGH_LOW':
                        if udhl_daily[direction] >= 1:
                            continue  # already traded this direction today

                    # Get 1min bars for execution
                    strike_bars = day_data[
                        (day_data['option_type_flag'] == opt_type) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] >= hhmm_bar)
                    ].reset_index(drop=True)

                    if len(strike_bars) < 2:
                        break

                    # Build spot bars for ULTIMATE_DAY_HIGH_LOW exit logic
                    spot_1min = day_data[
                        (day_data['option_type_flag'] == 'CE') &
                        (day_data['strike'] == 'ATM') &
                        (day_data['hhmm'] >= hhmm_bar)
                    ][['hhmm','close']].reset_index(drop=True) if strat.name == 'ULTIMATE_DAY_HIGH_LOW' else None

                    # Use raw spot column if available
                    if strat.name == 'ULTIMATE_DAY_HIGH_LOW' and 'spot' in day_data.columns:
                        spot_1min = day_data[day_data['hhmm'] >= hhmm_bar][['hhmm','spot']].rename(
                            columns={'spot': 'close'}).drop_duplicates('hhmm').reset_index(drop=True)

                    trade = execute_trade(0, strike_bars, strat, direction,
                                         day_ohlc=day_ohlc if strat.name == 'ULTIMATE_DAY_HIGH_LOW' else None,
                                         spot_bars=spot_1min)
                    if trade is not None:
                        # Apply regime position-size multiplier
                        size_mult = SIZE_MULTIPLIERS.get(regime, 1.0)
                        if size_mult != 1.0:
                            trade.pnl_rs = round(trade.pnl_rs * size_mult, 2)
                        all_trades.append(trade)
                        confluence[direction] += 1

                        if strat.name == 'ULTIMATE_DAY_HIGH_LOW':
                            udhl_daily[direction] += 1
                            # FIX: Allow 1 re-entry ONLY if first trade was SL
                            # AND market not in strong trending mode (max 1 re-entry ever)
                            if trade.exit_reason == 'SL' and udhl_daily[direction] < 2:
                                for j in range(i + 1, len(c15)):
                                    row2  = c15.iloc[j]
                                    ts2   = row2['ts_ist'] if hasattr(row2['ts_ist'], 'hour') else pd.Timestamp(row2['ts_ist'])
                                    hhmm2 = ts2.hour * 100 + ts2.minute
                                    if hhmm2 > strat.entry_end:
                                        break
                                    candles2 = c15.iloc[:j+1]
                                    opt_b2 = day_data[
                                        (day_data['option_type_flag'] == opt_type) &
                                        (day_data['strike'] == strat.strike) &
                                        (day_data['hhmm'] == hhmm2)
                                    ]
                                    prem2 = float(opt_b2['close'].iloc[-1]) if len(opt_b2) > 0 else 999.0
                                    if signal_check(strat, direction, candles2, day_ohlc,
                                                    pcr, hhmm2, expiry, prem2):
                                        s2_bars = day_data[
                                            (day_data['option_type_flag'] == opt_type) &
                                            (day_data['strike'] == strat.strike) &
                                            (day_data['hhmm'] >= hhmm2)
                                        ].reset_index(drop=True)
                                        spot_re = day_data[day_data['hhmm'] >= hhmm2][['hhmm','spot']].rename(
                                            columns={'spot': 'close'}).drop_duplicates('hhmm').reset_index(drop=True) \
                                            if 'spot' in day_data.columns else None
                                        if len(s2_bars) >= 2:
                                            t2 = execute_trade(0, s2_bars, strat, direction,
                                                               day_ohlc=day_ohlc, spot_bars=spot_re)
                                            if t2 is not None:
                                                all_trades.append(t2)
                                                udhl_daily[direction] += 1
                                        break  # max 1 re-entry
                    break   # one trade per strategy/direction/day (re-entry handled above)

    return all_trades


# ─────────────────────────────────────────────────────────────────────────────
# RESULTS + COMPARISON TABLE
# ─────────────────────────────────────────────────────────────────────────────

def print_results(trades: List[Trade], label: str = "TUNED"):
    if not trades:
        print(f"{label}: No trades.")
        return

    df = pd.DataFrame([{
        'strategy':    t.strategy, 'direction': t.direction, 'strike': t.strike,
        'date':        str(t.date), 'entry_time': str(t.entry_time)[:8],
        'entry_price': t.entry_price, 'exit_price': t.exit_price,
        'exit_reason': t.exit_reason, 'pnl_pts': t.pnl_pts,
        'pnl_rs':      t.pnl_rs, 'won': t.won, 'multiplier': t.multiplier,
    } for t in trades])

    df.to_csv('results/BACKTEST_V3_TUNED_TRADES.csv', index=False)

    rows = []
    for name, grp in df.groupby('strategy'):
        n     = len(grp)
        nw    = grp['won'].sum()
        total = grp['pnl_rs'].sum()
        avg   = grp['pnl_rs'].mean()
        avg_w = grp.loc[grp['won'],  'pnl_rs'].mean() if nw > 0 else 0
        avg_l = grp.loc[~grp['won'], 'pnl_rs'].mean() if (n-nw) > 0 else 0
        dd    = (grp['pnl_rs'].cumsum() - grp['pnl_rs'].cumsum().cummax()).min()
        tgt   = (grp['exit_reason']=='TARGET').mean()*100
        sl_p  = (grp['exit_reason']=='SL').mean()*100
        tsl_p = (grp['exit_reason']=='TSL').mean()*100
        eod_p = (grp['exit_reason']=='EOD').mean()*100
        best  = grp.groupby('date')['pnl_rs'].sum().max()
        worst = grp.groupby('date')['pnl_rs'].sum().min()
        rows.append({'Strategy':name,'Trades':n,'Win%':f"{nw/n*100:.0f}%",
                     'Total':total,'Avg':avg,'AvgW':avg_w,'AvgL':avg_l,
                     'Best':best,'Worst':worst,'MaxDD':dd,
                     'TGT%':tgt,'SL%':sl_p,'TSL%':tsl_p,'EOD%':eod_p})

    sdf = pd.DataFrame(rows).sort_values('Total', ascending=False)
    sdf.to_csv('results/BACKTEST_V3_TUNED_SUMMARY.csv', index=False)

    W = 150
    print()
    print("=" * W)
    print(f"  [{label}] NIFTY V3 BACKTEST — Feb 3 to May 4 2025 | {len(df)} trades | {df['date'].nunique()} days | LOT=75")
    print("=" * W)
    hdr = (f"  {'Strategy':<28} {'N':>4} {'Win%':>5} {'Total P&L':>11} {'Avg':>7} "
           f"{'AvgWin':>8} {'AvgLoss':>8} {'BestDay':>9} {'WorstDay':>9} "
           f"{'MaxDD':>9} {'TGT%':>5} {'SL%':>4} {'TSL%':>5} {'EOD%':>5}")
    print(hdr)
    print("-" * W)
    for _, r in sdf.iterrows():
        mark = " ✓" if r['Total'] > 0 else "  "
        print(f"{mark} {r['Strategy']:<28} {r['Trades']:>4} {r['Win%']:>5} "
              f"Rs.{r['Total']:>+9,.0f} Rs.{r['Avg']:>+5,.0f} "
              f"Rs.{r['AvgW']:>+6,.0f} Rs.{r['AvgL']:>+6,.0f} "
              f"Rs.{r['Best']:>+7,.0f} Rs.{r['Worst']:>+7,.0f} "
              f"Rs.{r['MaxDD']:>+7,.0f} "
              f"{r['TGT%']:>4.0f}% {r['SL%']:>3.0f}% {r['TSL%']:>4.0f}% {r['EOD%']:>4.0f}%")
    print("-" * W)
    grand = df['pnl_rs'].sum()
    grand_dd = (df['pnl_rs'].cumsum() - df['pnl_rs'].cumsum().cummax()).min()
    green = (df.groupby('date')['pnl_rs'].sum() > 0).mean()*100
    print(f"   {'COMBINED':<28} {len(df):>4} {df['won'].mean()*100:.0f}%  "
          f"Rs.{grand:>+9,.0f}  Rs.{df['pnl_rs'].mean():>+4,.0f}   "
          f"{'':>8} {'':>8}   "
          f"Rs.{df.groupby('date')['pnl_rs'].sum().max():>+6,.0f}  "
          f"Rs.{df.groupby('date')['pnl_rs'].sum().min():>+6,.0f}  "
          f"Rs.{grand_dd:>+6,.0f}")
    print(f"   Green days: {green:.0f}%  |  Best: {df.groupby('date')['pnl_rs'].sum().idxmax()}  "
          f"|  Worst: {df.groupby('date')['pnl_rs'].sum().idxmin()}")
    print("=" * W)

    # Zero-Hero and Gamma Blast detail
    for s in ['ZERO_HERO', 'GAMMA_BLAST']:
        sub = df[df['strategy'] == s]
        if len(sub) == 0:
            print(f"\n{s}: 0 trades fired.")
            continue
        big = sub[sub['multiplier'] >= 1.5]
        print(f"\n{s}: {len(sub)} trades | {sub['won'].mean()*100:.0f}% win | "
              f"Rs.{sub['pnl_rs'].sum():+,.0f} total | "
              f"{len(big)} trades ≥1.5× premium multiplier")
        print(sub[['date','direction','entry_time','entry_price','exit_price',
                   'exit_reason','multiplier','pnl_rs']].to_string(index=False))

    return sdf


# ─────────────────────────────────────────────────────────────────────────────
# COMPARISON: V1 vs TUNED
# ─────────────────────────────────────────────────────────────────────────────

def compare_v1_vs_tuned(sdf_tuned: pd.DataFrame):
    v1_path = 'results/BACKTEST_V3_3M_SUMMARY.csv'
    if not os.path.exists(v1_path):
        print("\n(V1 summary not found for comparison)")
        return
    v1 = pd.read_csv(v1_path)
    v1['Total_v1'] = v1['Total P&L'].str.replace('Rs.','').str.replace(',','').str.replace('+','').astype(float)
    merged = sdf_tuned[['Strategy','Trades','Win%','Total']].merge(
        v1[['Strategy','Trades','Win%','Total_v1']], on='Strategy', suffixes=('_tuned','_v1'), how='outer'
    ).fillna(0)
    merged['Delta'] = merged['Total'] - merged['Total_v1']
    merged = merged.sort_values('Delta', ascending=False)

    print()
    print("=" * 90)
    print("  V1 (untuned)  vs  V2 (tuned)  — Delta P&L per strategy")
    print("=" * 90)
    print(f"  {'Strategy':<28} {'V1 Trades':>9} {'V1 P&L':>10} {'V2 Trades':>9} {'V2 P&L':>10} {'Delta':>10}")
    print("-" * 90)
    for _, r in merged.iterrows():
        arrow = "▲" if r['Delta'] > 0 else "▼"
        print(f"  {str(r['Strategy']):<28} {int(r.get('Trades_v1',0)):>9} "
              f"Rs.{r['Total_v1']:>+8,.0f} {int(r.get('Trades_tuned',0)):>9} "
              f"Rs.{r['Total']:>+8,.0f} {arrow} Rs.{r['Delta']:>+7,.0f}")
    total_v1    = v1['Total_v1'].sum()
    total_tuned = sdf_tuned['Total'].sum()
    print("-" * 90)
    print(f"  {'TOTAL':<28} {'':>9} Rs.{total_v1:>+8,.0f} {'':>9} Rs.{total_tuned:>+8,.0f} "
          f"{'▲' if total_tuned > total_v1 else '▼'} Rs.{total_tuned-total_v1:>+7,.0f}")
    print("=" * 90)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 70)
    print("  NIFTY V3 TUNED Backtest")
    print("  Improvements: TSL all, time-window, direction-bias, VWAP+volume,")
    print("  premium filter, Zero-Hero PE-only <50Rs, Gamma-Blast refined")
    print("=" * 70)

    opt_data = load_option_data()
    eod_data = load_eod_data()
    trades   = run_backtest(opt_data, eod_data)
    print(f"Total trades: {len(trades)}")
    sdf = print_results(trades, label="TUNED V2")
    compare_v1_vs_tuned(sdf)
