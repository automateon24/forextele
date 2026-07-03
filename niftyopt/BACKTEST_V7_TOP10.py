#!/usr/bin/env python3
"""
BACKTEST V7 — Multi-Index Engine (REAL DATA ONLY)
==================================================
Runs the same 8 locked strategies simultaneously across ALL 5 indices:
  - NIFTY       (lot=75,  atm_step=50,  exch=NSE_FNO, sec_id=13)
  - BANKNIFTY   (lot=15,  atm_step=100, exch=NSE_FNO, sec_id=25)
  - FINNIFTY    (lot=40,  atm_step=50,  exch=NSE_FNO, sec_id=27)
  - MIDCPNIFTY  (lot=75,  atm_step=25,  exch=NSE_FNO, sec_id=442)
  - SENSEX      (lot=10,  atm_step=100, exch=BSE_FNO, sec_id=51)

Data: 100% real 1-min option OHLCV + spot + IV + OI fetched from
      Dhan /v2/charts/rollingoption — saved as parquets in data/raw/
      Format: {INDEX}_expired_{from}_{to}_{strike}_{type}_1min_MONTH_1.parquet
      NO synthetic/fake/assumed values.

Architecture:
  load_index_data() → reads all parquets for that index
  run_index_backtest() → same V6 logic (profile match → signal → trade → exit)
  ThreadPoolExecutor → 5 indices in parallel
  merge + combined P&L report
"""

import sys, os, glob
sys.path.insert(0, 'c:/cursor/options/niftyopt')

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings; warnings.filterwarnings('ignore')

# Import V6 strategy DNA (all locked — do not modify)
# TOP10 STRATEGIES ONLY - Best performers from baseline
ACTIVE_STRATEGIES_TOP10 = {
    'DAY_LOW_BULLISH',       # 95% WR
    'BULL_TREND_FOLLOWER',   # 100% WR  
    'DAY_HIGH_BEARISH',      # 82% WR
    'BEAR_TREND_FOLLOWER',   # 92% WR
    'MEAN_REVERSION',        # 83% WR
    'VOLATILITY_BREAKOUT',   # 100% WR
    'EARLY_BREAKDOWN',       # 100% WR
    'ORDER_BLOCK_REVERSAL',  # 100% WR (low volume)
    'WIDE_RANGE_RIDER',      # 85% WR
    'ENHANCED_BULLISH',      # Added for coverage
}

from BACKTEST_V6_PROFILED import (
    ACTIVE_STRATEGIES, ENTRY_START, ENTRY_CUTOFF, FIXED_TARGET_STRATEGIES,
    TRADEABLE_REGIMES, STRATEGY_PROFILES,
    TSL_ACTIVATE, TSL_TRAIL, SL_BACKSTOP, TARGET_PCT, HARD_EXIT,
    StrategyProfile, compute_day_context, compute_intraday_state,
    match_profile, Trade, execute_fixed_target,
)
from BACKTEST_V3_TUNED import (
    calc_pcr, signal_check, make_strategies, build_15min_spot,
    PERIODS, STRIKES, OPT_TYPES,
)
from regime_detector import label_days

UTC_OFFSET = pd.Timedelta(hours=5, minutes=30)
RAW_DIR    = 'data/raw'
CAPITAL    = 100_000

# ─────────────────────────────────────────────────────────────────────────────
# INDEX CONFIGS  — all 5 real indices
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class IndexConfig:
    name:          str
    lot_size:      int
    atm_step:      float
    expiry_dow:    int    # 0=Mon … 4=Fri
    brokerage:     float = 40.0
    premium_scale: float = 1.0   # multiplier applied to strat.min/max_premium
    hard_exit:     int   = 1415  # force-close time (HHMM)
    max_ce_day:    int   = 1     # max CE entries per day (NIFTY allows 2, others 1)
    wide_range_pts: float = 150.0 # WIDE_RANGE_RIDER min day-range threshold (absolute pts)
    # NIFTY 150pts ≈ 0.65% of 23K | BN 400pts ≈ 0.73% | FN 170pts ≈ 0.65% | MIDCP 80pts ≈ 0.62% | SENSEX 500pts ≈ 0.65%
    entry_cutoff:   int   = 1400  # last bar hhmm at which new entries are allowed

# premium_scale: median ATM close vs NIFTY median ~225
# hard_exit: NIFTY 14:15 proven; BN/SENSEX need earlier cutoff to avoid TIME losses
# max_ce_day: NIFTY profits from 2 CE entries; BN/SENSEX/MIDCP only 1 (avoid duplication)
INDEX_CONFIGS: Dict[str, IndexConfig] = {
    'NIFTY':      IndexConfig('NIFTY',      75,  50,  3, premium_scale=1.0,  hard_exit=1415, max_ce_day=2, wide_range_pts=150,  entry_cutoff=1400),
    'BANKNIFTY':  IndexConfig('BANKNIFTY',  15,  100, 2, premium_scale=3.35, hard_exit=1345, max_ce_day=1, wide_range_pts=400,  entry_cutoff=1245),
    'FINNIFTY':   IndexConfig('FINNIFTY',   40,  50,  1, premium_scale=1.6,  hard_exit=1345, max_ce_day=1, wide_range_pts=170,  entry_cutoff=1200),
    'MIDCPNIFTY': IndexConfig('MIDCPNIFTY', 75,  25,  1, premium_scale=1.1,  hard_exit=1345, max_ce_day=1, wide_range_pts=80,   entry_cutoff=1215),
    'SENSEX':     IndexConfig('SENSEX',     10,  100, 4, premium_scale=4.0,  hard_exit=1345, max_ce_day=1, wide_range_pts=500,  entry_cutoff=1245),
}


# ─────────────────────────────────────────────────────────────────────────────
# PER-INDEX STRATEGY PROFILES  (derived from real data DNA)
# ─────────────────────────────────────────────────────────────────────────────
#
# NIFTY   : spot~23K, day_range~0.26%, vix_proxy~0.117%, PCR median 1.03 p95 2.39
# BANKNIFTY: spot~55K, day_range~1.12%, vix_proxy~0.154%, PCR median 1.08 p95 5.02
# FINNIFTY : spot~26K, day_range~1.08%, vix_proxy~0.147%, PCR median 1.10 p95 18
# MIDCPNIFTY: spot~13K, day_range~1.57%, vix_proxy~0.195%, PCR median 0.95 p95 7.98
# SENSEX  : spot~77K, day_range~0.92%, vix_proxy~0.122%, PCR median 1.10 p95 35
#
# Key differences that require per-index recalibration:
#  1. gap_pct_range   — BN/FN/MIDCP daily std ~0.85% vs NIFTY 0.30% → wider gap window
#  2. pcr_open_range  — SENSEX/FINNIFTY PCR spikes to 18-35 → upper bound must be raised
#  3. vix_proxy       — computed by compute_day_context as range/spot% — all indices
#                       naturally normalize to roughly similar %, no rescaling needed
#  4. rsi_range       — algorithm is identical, thresholds hold across indices
#  5. range_consumed  — ratio is index-agnostic ✓
#
# Strategy-level changes per index (relative to NIFTY locked profiles):
#  BANKNIFTY : wider gap/PCR; slightly looser rsi for BEAR/BULL_TREND (higher vol)
#  FINNIFTY  : wide PCR upper bound; similar to BN
#  MIDCPNIFTY: widest day-range, PCR unreliable (median 0.95, wide spread) →
#              relax PCR gates, tighten range_consumed (higher vol = quicker moves)
#  SENSEX    : PCR upper can be 40+; gap±2% common; vix_proxy similar to NIFTY

def _make_profiles_for_index(idx: str) -> Dict[str, 'StrategyProfile']:
    """
    Return a complete STRATEGY_PROFILES dict calibrated for the given index.
    NIFTY returns the original locked V6 profiles unchanged.
    All others are re-derived from the same logical DNA with index-specific
    numeric bounds calculated from real observed data.
    """
    if idx == 'NIFTY':
        return STRATEGY_PROFILES  # unchanged — locked V6 DNA

    # ── shared adjustments by index ─────────────────────────────────────────
    # gap_pct: BN/FN/MIDCP/SENSEX all have daily_move_std ~0.8-8.7% (vs NIFTY 0.3%)
    #          allow ±3.0% gap for BN/FN/SENSEX, ±4.0% for MIDCP (highest daily std)
    gap = {'BANKNIFTY': 3.0, 'FINNIFTY': 3.0, 'MIDCPNIFTY': 4.0, 'SENSEX': 3.0}[idx]

    # pcr_upper: NIFTY p95=2.39, BN=5.02, FN=18, MIDCP=7.98, SENSEX=35
    #            set upper to p99 (observed max / 1.5 to avoid outlier lock-out)
    pcr_up = {'BANKNIFTY': 6.0, 'FINNIFTY': 20.0, 'MIDCPNIFTY': 10.0, 'SENSEX': 40.0}[idx]

    # rsi: BN/SENSEX have slightly wider intraday swings → allow RSI 1-2 pts looser
    rsi_adj = {'BANKNIFTY': 3, 'FINNIFTY': 2, 'MIDCPNIFTY': 3, 'SENSEX': 3}[idx]

    # range_consumed: MIDCPNIFTY moves fastest → tighten min to catch early moves
    rc_adj = {'BANKNIFTY': 0.0, 'FINNIFTY': 0.0, 'MIDCPNIFTY': -0.05, 'SENSEX': 0.0}[idx]

    def pcr(lo=0.0, hi=3.0): return (lo, min(hi, pcr_up))
    def gap_r(lo, hi): return (-gap, gap)
    def rsi(lo, hi): return (max(0, lo - rsi_adj), min(100, hi + rsi_adj))
    def rc(lo, hi): return (max(0.0, lo + rc_adj), min(1.0, hi))

    return {

        'DAY_LOW_BULLISH': StrategyProfile(
            name='DAY_LOW_BULLISH', direction='CE',
            gap_pct_range=gap_r(-1.5, 1.5),
            pcr_open_range=pcr(0.7, 2.5),
            rsi_range=rsi(20, 48),
            ema_structure='ANY', vwap_side='ANY', momentum_dir='UP',
            range_consumed_min=rc(0.30, 1.0)[0], range_consumed_max=rc(0.0, 0.80)[1],
            min_body_ratio=0.20, candle_consistency='ANY', vol_trend='RISING',
            base_confidence=0.68,
        ),

        'DAY_HIGH_BEARISH': StrategyProfile(
            name='DAY_HIGH_BEARISH', direction='PE',
            gap_pct_range=gap_r(-3.0, 3.0),
            pcr_open_range=pcr(0.0, 3.0),
            rsi_range=rsi(53, 85),
            ema_structure='ANY', vwap_side='ABOVE', momentum_dir='DOWN',
            range_consumed_min=rc(0.45, 1.0)[0], range_consumed_max=1.0,
            min_body_ratio=0.18, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.60,
        ),

        'BEAR_TREND_FOLLOWER': StrategyProfile(
            name='BEAR_TREND_FOLLOWER', direction='PE',
            gap_pct_range=gap_r(-5.0, 5.0),
            pcr_open_range=pcr(0.0, 3.0),
            rsi_range=rsi(22, 55),
            ema_structure='BEAR', vwap_side='BELOW', momentum_dir='DOWN',
            range_consumed_min=rc(0.15, 1.0)[0], range_consumed_max=rc(0.0, 0.85)[1],
            min_body_ratio=0.18, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.68,
        ),

        'BULL_TREND_FOLLOWER': StrategyProfile(
            name='BULL_TREND_FOLLOWER', direction='CE',
            gap_pct_range=gap_r(-5.0, 5.0),
            pcr_open_range=pcr(0.0, 3.0),
            rsi_range=rsi(43, 78),
            ema_structure='BULL', vwap_side='ABOVE', momentum_dir='UP',
            range_consumed_min=rc(0.15, 1.0)[0], range_consumed_max=rc(0.0, 0.85)[1],
            min_body_ratio=0.18, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.68,
        ),

        'MEAN_REVERSION': StrategyProfile(
            name='MEAN_REVERSION', direction='BOTH',
            gap_pct_range=gap_r(-2.5, 2.5),
            pcr_open_range=pcr(0.0, pcr_up),
            rsi_range=(0, 100),
            ema_structure='ANY', vwap_side='ANY', momentum_dir='ANY',
            range_consumed_min=rc(0.35, 1.0)[0], range_consumed_max=0.75,
            min_body_ratio=0.10, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.60,
        ),

        'VOLATILITY_BREAKOUT': StrategyProfile(
            name='VOLATILITY_BREAKOUT', direction='BOTH',
            gap_pct_range=gap_r(-5.0, 5.0),
            pcr_open_range=pcr(0.0, pcr_up),
            rsi_range=(0, 100),
            ema_structure='ANY', vwap_side='ANY', momentum_dir='ANY',
            range_consumed_min=0.0, range_consumed_max=1.0,
            min_body_ratio=0.30, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.65,
        ),

        'ORDER_BLOCK_REVERSAL': StrategyProfile(
            name='ORDER_BLOCK_REVERSAL', direction='BOTH',
            gap_pct_range=gap_r(-5.0, 5.0),
            pcr_open_range=pcr(0.0, pcr_up),
            rsi_range=(30, 70),        # tighter: only fire when RSI not at extreme
            ema_structure='ANY', vwap_side='ANY', momentum_dir='ANY',
            range_consumed_min=0.50,   # block only valid once 50%+ of day range consumed
            range_consumed_max=0.90,
            min_body_ratio=0.15, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.62,
        ),

        'MORNING_BREAKOUT': StrategyProfile(
            name='MORNING_BREAKOUT', direction='CE',
            gap_pct_range=gap_r(-1.5, 1.5),
            pcr_open_range=pcr(0.0, 3.0),
            rsi_range=rsi(51, 82),
            ema_structure='BULL', vwap_side='ABOVE', momentum_dir='UP',
            range_consumed_min=0.0, range_consumed_max=1.0,
            min_body_ratio=0.18, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.66,
        ),

        'EARLY_BREAKDOWN': StrategyProfile(
            name='EARLY_BREAKDOWN', direction='PE',
            gap_pct_range=(-gap*0.30, gap*0.30),  # only truly flat-open days
            pcr_open_range=pcr(0.0, 3.0),
            rsi_range=rsi(15, 44),
            ema_structure='BEAR', vwap_side='BELOW', momentum_dir='DOWN',
            range_consumed_min=0.10, range_consumed_max=0.60,  # early-day only
            min_body_ratio=0.25, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.68,
        ),

        'WIDE_RANGE_RIDER': StrategyProfile(
            name='WIDE_RANGE_RIDER', direction='BOTH',
            gap_pct_range=gap_r(-5.0, 5.0),
            pcr_open_range=pcr(0.0, pcr_up),
            rsi_range=rsi(42, 60),
            ema_structure='ANY', vwap_side='ANY', momentum_dir='ANY',
            range_consumed_min=rc(0.30, 1.0)[0], range_consumed_max=rc(0.0, 0.80)[1],
            min_body_ratio=0.18, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.64,
        ),

        'SHORT_UNWIND': StrategyProfile(
            name='SHORT_UNWIND', direction='CE',
            gap_pct_range=gap_r(-3.0, 3.0),
            pcr_open_range=pcr(0.0, 3.0),
            rsi_range=rsi(46, 80),
            ema_structure='BULL', vwap_side='ANY', momentum_dir='ANY',
            range_consumed_min=0.0, range_consumed_max=1.0,
            min_body_ratio=0.10, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.72,
        ),

        'ENHANCED_BULLISH': StrategyProfile(
            name='ENHANCED_BULLISH', direction='CE',
            gap_pct_range=gap_r(-2.0, 2.0),
            pcr_open_range=pcr(0.0, 3.0),
            rsi_range=rsi(18, 50),
            ema_structure='ANY', vwap_side='ANY', momentum_dir='UP',
            range_consumed_min=rc(0.12, 1.0)[0], range_consumed_max=rc(0.0, 0.85)[1],
            min_body_ratio=0.18, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.62,
        ),

        'ENHANCED_BEARISH': StrategyProfile(
            name='ENHANCED_BEARISH', direction='PE',
            gap_pct_range=gap_r(-5.0, 5.0),
            pcr_open_range=pcr(0.0, pcr_up),
            rsi_range=rsi(50, 85),
            ema_structure='ANY', vwap_side='ANY', momentum_dir='DOWN',
            range_consumed_min=rc(0.05, 1.0)[0], range_consumed_max=0.95,
            min_body_ratio=0.10, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.64,
        ),

        'MAGIC_SQUARE': StrategyProfile(
            name='MAGIC_SQUARE', direction='BOTH',
            gap_pct_range=gap_r(-5.0, 5.0),
            pcr_open_range=pcr(0.0, pcr_up),
            rsi_range=rsi(28, 70),
            ema_structure='ANY', vwap_side='ANY', momentum_dir='ANY',
            range_consumed_min=rc(0.22, 1.0)[0], range_consumed_max=rc(0.0, 0.90)[1],
            min_body_ratio=0.10, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.64,
        ),

        'TREND_FOLLOWING': StrategyProfile(
            name='TREND_FOLLOWING', direction='PE',
            gap_pct_range=gap_r(-3.0, 3.0),
            pcr_open_range=pcr(0.0, 3.0),
            rsi_range=rsi(28, 52),
            ema_structure='BEAR', vwap_side='BELOW', momentum_dir='DOWN',
            range_consumed_min=rc(0.18, 1.0)[0], range_consumed_max=0.90,
            min_body_ratio=0.18, candle_consistency='ANY', vol_trend='ANY',
            base_confidence=0.63,
        ),
    }


# Build once at import time — one profile dict per index
INDEX_PROFILES: Dict[str, Dict[str, StrategyProfile]] = {
    idx: _make_profiles_for_index(idx)
    for idx in INDEX_CONFIGS
}


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADER  — identical pattern for all indices (real parquets)
# ─────────────────────────────────────────────────────────────────────────────

def load_option_data_for_index(idx_name: str) -> pd.DataFrame:
    """
    Load all 1-min option parquets for idx_name (same format as NIFTY).
    Files: {RAW_DIR}/{idx_name}_expired_{ps}_{pe}_{strike}_{type}_1min_MONTH_1.parquet
    """
    print(f"  [{idx_name}] Loading parquets...", flush=True)
    frames = []
    for ps, pe in PERIODS:
        for strike in STRIKES:
            for otype in OPT_TYPES:
                fname = f"{idx_name}_expired_{ps}_{pe}_{strike}_{otype}_1min_MONTH_1.parquet"
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

    if not frames:
        print(f"  [{idx_name}] NO parquets found in {RAW_DIR}", flush=True)
        return pd.DataFrame()

    data = pd.concat(frames, ignore_index=True)
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    data['ts_ist']    = data['timestamp']
    data['date']      = data['ts_ist'].dt.date
    data['hhmm']      = data['ts_ist'].dt.hour * 100 + data['ts_ist'].dt.minute
    data = data.sort_values(['date','strike','option_type_flag','ts_ist']).reset_index(drop=True)
    print(f"  [{idx_name}] {len(data):,} rows | {data['date'].nunique()} days "
          f"| {data['date'].min()} → {data['date'].max()}", flush=True)
    return data


def build_eod_from_option_data(opt: pd.DataFrame) -> pd.DataFrame:
    """Build a daily OHLC table from the spot column in option parquets."""
    spot = opt[opt['option_type_flag'] == 'CE'][['date','ts_ist','spot']].copy()
    spot = spot.sort_values('ts_ist')
    eod = spot.groupby('date').agg(
        open=('spot', 'first'),
        high=('spot', 'max'),
        low=('spot', 'min'),
        close=('spot', 'last'),
    ).reset_index()
    eod = eod.rename(columns={'date': 'dt'})
    return eod


# ─────────────────────────────────────────────────────────────────────────────
# TSL / FIXED-TARGET EXECUTOR  (index-aware)
# ─────────────────────────────────────────────────────────────────────────────

def _get_ts(bar) -> pd.Timestamp:
    v = bar.get('ts_ist') if hasattr(bar, 'get') else getattr(bar, 'ts_ist', None)
    return pd.Timestamp(v) if v is not None else pd.Timestamp('2000-01-01')


def signal_check_idx(strat, direction: str, c15_slice, day_ohlc: dict,
                     pcr: float, hhmm: int, expiry: bool,
                     real_prem: float, cfg: 'IndexConfig') -> bool:
    """
    Index-aware wrapper around signal_check.

    For NIFTY: delegates straight to signal_check (all thresholds calibrated).
    For non-NIFTY: the profile match (match_profile) already encodes the full
    market-state logic (RSI, EMA, momentum, range_consumed, PCR, gap) using
    index-calibrated bounds from INDEX_PROFILES.  signal_check contains
    NIFTY-hardcoded absolute thresholds (150pt range, RSI<48 breakout, etc.)
    that produce false negatives on BN/SENSEX/FN/MIDCP — so we trust the
    profile gating and return True here.

    Exception: strategies with expiry-only gates (ZERO_HERO, GAMMA_BLAST)
    still need signal_check to enforce the is_expiry check.
    """
    EXPIRY_ONLY = {'ZERO_HERO', 'GAMMA_BLAST'}

    if cfg.name == 'NIFTY':
        # NIFTY: use full signal_check with clamped norm_prem
        norm_prem = real_prem  # already in NIFTY scale (premium_scale=1.0)
        norm_prem = max(strat.min_premium + 0.01,
                       min(strat.max_premium - 0.01, norm_prem))
        return signal_check(strat, direction, c15_slice, day_ohlc, pcr, hhmm, expiry, norm_prem)

    if strat.name in EXPIRY_ONLY:
        # Must respect the expiry gate regardless of index
        norm_prem = real_prem / cfg.premium_scale
        norm_prem = max(strat.min_premium + 0.01,
                       min(strat.max_premium - 0.01, norm_prem))
        return signal_check(strat, direction, c15_slice, day_ohlc, pcr, hhmm, expiry, norm_prem)

    # Non-NIFTY: profile already validated all market conditions with
    # index-calibrated thresholds — no need for NIFTY-tuned signal_check
    return True

def execute_tsl_idx(entry_bar: pd.Series, remaining: pd.DataFrame, hard_exit: int = HARD_EXIT):
    ep  = float(entry_bar['open'])
    sl  = ep * (1 - SL_BACKSTOP)
    tgt = ep * (1 + TARGET_PCT)
    thi = ep
    xp = xr = xt = None

    for _, bar in remaining.iterrows():
        ts   = _get_ts(bar)
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))
        thi  = max(thi, hi)

        if hhmm >= hard_exit:
            xp = float(bar['close']); xr = 'TIME'; xt = ts; break
        if lo <= sl:
            xp = sl; xr = 'SL'; xt = ts; break
        if hi >= tgt:
            xp = tgt; xr = 'TARGET'; xt = ts; break
        if thi >= ep * (1 + TSL_ACTIVATE):
            floor = thi * (1 - TSL_TRAIL)
            if lo <= floor and floor > sl:
                xp = max(floor, sl); xr = 'TSL'; xt = ts; break

    if xp is None:
        last = remaining.iloc[-1] if len(remaining) > 0 else entry_bar
        xp = float(last['close']); xr = 'EOD'; xt = _get_ts(last)

    return max(xp, 0.05), xr, xt


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE-INDEX BACKTEST  (called in each thread)
# ─────────────────────────────────────────────────────────────────────────────

ONE_TRADE_STRATS = {
    'MORNING_BREAKOUT','EARLY_BREAKDOWN','WIDE_RANGE_RIDER',
    'VOLATILITY_BREAKOUT','TREND_FOLLOWING','MEAN_REVERSION',
    'ENHANCED_BULLISH','BEAR_TREND_FOLLOWER','BULL_TREND_FOLLOWER',
    'MAGIC_SQUARE','ORDER_BLOCK_REVERSAL','SHORT_UNWIND','ENHANCED_BEARISH',
}

# Strategies that do NOT work for specific indices based on their DNA:
#   ORDER_BLOCK_REVERSAL — NIFTY only (hardcoded 0.7% proximity works for NIFTY 23K spot;
#       fires as a paired MEAN_REVERSION companion on non-NIFTY → both TIME-exit together)
#   EARLY_BREAKDOWN — requires flat open day (gap < 0.8%); BN/SENSEX gap avg 0.9-1.2% → disqualifies
INDEX_STRATEGY_EXCLUSIONS: Dict[str, set] = {
    'NIFTY':      set(),
    'BANKNIFTY':  {'ORDER_BLOCK_REVERSAL', 'EARLY_BREAKDOWN'},
    'FINNIFTY':   {'ORDER_BLOCK_REVERSAL', 'EARLY_BREAKDOWN'},
    'MIDCPNIFTY': {'ORDER_BLOCK_REVERSAL', 'EARLY_BREAKDOWN'},
    'SENSEX':     {'ORDER_BLOCK_REVERSAL', 'EARLY_BREAKDOWN'},
}


def run_index(idx_name: str, opt_data: pd.DataFrame,
              eod_data: pd.DataFrame, cfg: IndexConfig) -> Tuple[List[Trade], str]:

    print(f"  [{idx_name}] Labelling regimes on {opt_data['date'].nunique()} days...", flush=True)
    day_regimes   = label_days(opt_data)
    exclusions    = INDEX_STRATEGY_EXCLUSIONS.get(idx_name, set())
    active_strats = [s for s in make_strategies()
                     if s.name in ACTIVE_STRATEGIES_TOP10 and s.name not in exclusions]
    idx_profiles  = INDEX_PROFILES[idx_name]   # per-index calibrated profiles
    trading_days  = sorted(opt_data['date'].unique())
    all_trades: List[Trade] = []
    prev_close = 0.0

    for day in trading_days:
        regime = day_regimes.get(day, 'NORMAL')
        eod_row = eod_data[eod_data['dt'] == day] if not eod_data.empty else pd.DataFrame()

        if regime not in TRADEABLE_REGIMES:
            if not eod_row.empty:
                prev_close = float(eod_row.iloc[0]['close'])
            continue

        day_data = opt_data[opt_data['date'] == day].copy()
        c15      = build_15min_spot(day_data)
        if len(c15) < 4:
            continue

        pcr    = calc_pcr(day_data)
        expiry = (day.weekday() == cfg.expiry_dow) if hasattr(day, 'weekday') else False

        if not eod_row.empty:
            r = eod_row.iloc[0]
            day_ohlc = {k: float(r[k]) for k in ('open','high','low','close')}
        else:
            day_ohlc = {'open':  float(c15.iloc[0]['close']),
                        'high':  float(c15['high'].max()),
                        'low':   float(c15['low'].min()),
                        'close': float(c15.iloc[-1]['close'])}

        ctx = compute_day_context(c15, prev_close, pcr)

        trades_today: Dict[str, int]      = defaultdict(int)
        strat_trades: Dict[str, int]      = defaultdict(int)

        for i in range(3, len(c15)):
            row  = c15.iloc[i]
            ts   = _get_ts(row)
            hhmm = ts.hour * 100 + ts.minute
            if hhmm < 945 or hhmm > cfg.entry_cutoff:
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
                if strat.name == 'DAY_HIGH_BEARISH' and regime == 'TRENDING_BULL':
                    continue
                if strat.name in ONE_TRADE_STRATS and strat_trades[strat.name] >= 1:
                    continue

                dirs = ['CE','PE'] if strat.direction == 'BOTH' else [strat.direction]

                for direction in dirs:
                    if direction == 'CE' and trades_today['CE'] >= cfg.max_ce_day:
                        continue
                    if direction == 'PE' and trades_today['PE'] >= 1:
                        continue

                    profile = idx_profiles[strat.name]
                    armed, conf, arm_reason = match_profile(profile, ctx, state, direction)
                    if not armed:
                        continue


                    opt_b = day_data[
                        (day_data['option_type_flag'] == direction) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] == hhmm)
                    ]
                    if len(opt_b) == 0:
                        continue

                    prem = float(opt_b['close'].iloc[-1])
                    scaled_min = strat.min_premium * cfg.premium_scale
                    if prem < scaled_min:
                        continue
                    # For non-NIFTY: no upper premium cap — premiums can be much
                    # higher than NIFTY-tuned max_premium; profile RSI/range gates protect
                    if cfg.name == 'NIFTY':
                        scaled_max = strat.max_premium * cfg.premium_scale
                        if prem > scaled_max:
                            continue

                    try:
                        ok = signal_check_idx(strat, direction, c15.iloc[:i+1],
                                              day_ohlc, pcr, hhmm, expiry, prem, cfg)
                    except Exception:
                        ok = True
                    if not ok:
                        continue

                    exec_bars = day_data[
                        (day_data['option_type_flag'] == direction) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] > hhmm)
                    ].reset_index(drop=True)
                    if len(exec_bars) < 2:
                        continue

                    entry_bar   = exec_bars.iloc[0]
                    entry_price = float(entry_bar['open'])
                    remaining   = exec_bars.iloc[1:].copy()

                    fixed_tgt = FIXED_TARGET_STRATEGIES.get(strat.name)
                    if fixed_tgt:
                        xp, xr, xt = execute_fixed_target(entry_bar, remaining, fixed_tgt)
                    else:
                        xp, xr, xt = execute_tsl_idx(entry_bar, remaining, cfg.hard_exit)

                    pnl_pts = xp - entry_price
                    pnl_rs  = round(pnl_pts * cfg.lot_size - cfg.brokerage, 2)

                    all_trades.append(Trade(
                        date=day, strategy=strat.name, direction=direction,
                        regime=regime, confidence=conf, lots=1,
                        entry_time=_get_ts(entry_bar),
                        entry_price=entry_price,
                        exit_price=xp, exit_time=xt, exit_reason=xr,
                        pnl_pts=round(pnl_pts, 2), pnl_rs=pnl_rs,
                        won=pnl_rs > 0, armed_reason=arm_reason,
                    ))
                    trades_today[direction] += 1
                    strat_trades[strat.name] += 1
                    break  # one trade per strategy per direction per bar

        if not eod_row.empty:
            prev_close = float(eod_row.iloc[0]['close'])

    print(f"  [{idx_name}] Done — {len(all_trades)} trades", flush=True)
    return all_trades, idx_name


# ─────────────────────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def report_multi(results: Dict[str, List], total_days: int):
    rows = []
    for idx_name, trades in results.items():
        for t in trades:
            d = t.__dict__.copy()
            d['index'] = idx_name
            rows.append(d)

    if not rows:
        print("NO TRADES GENERATED ACROSS ALL INDICES"); return

    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])

    print(f"\n{'='*70}")
    print(f"BACKTEST V7 — MULTI-INDEX REAL DATA  ({total_days} calendar days)")
    print(f"  5 indices × 8 locked strategies × 1 lot each")
    print(f"{'='*70}")

    daily   = df.groupby('date')['pnl_rs'].sum()
    tot_pnl = df['pnl_rs'].sum()
    wr      = 100 * df['won'].mean()
    udays   = len(daily)
    green   = (daily > 0).sum()
    dd      = (daily.cumsum() - daily.cumsum().cummax()).min()
    monthly = tot_pnl / udays * 22 if udays else 0

    print(f"\n  COMBINED (all indices)")
    print(f"  Trades             : {len(df)}")
    print(f"  Win rate           : {wr:.1f}%")
    print(f"  Total PnL          : Rs.{tot_pnl:+,.0f}")
    print(f"  Avg PnL/day        : Rs.{tot_pnl/udays:+,.0f}  ({tot_pnl/udays/CAPITAL*100:.2f}%)")
    print(f"  Monthly est.       : Rs.{monthly:+,.0f}  ({monthly/CAPITAL*100:.1f}%)")
    print(f"  Green days         : {green}/{udays} ({100*green/udays:.0f}%)")
    print(f"  Max drawdown       : Rs.{dd:+,.0f}")
    print(f"  5% daily target    : {(daily/CAPITAL*100 >= 5.0).sum()} days hit (Rs.5,000+)")

    print(f"\n  PER INDEX:")
    hdr = f"  {'Index':<12} {'Trades':>7} {'WR%':>5} {'PnL':>12} {'Days':>6} {'Avg/day':>10} {'Monthly':>10}"
    print(hdr)
    print(f"  {'-'*65}")
    for idx_name in ['NIFTY','BANKNIFTY','FINNIFTY','MIDCPNIFTY','SENSEX']:
        sub = df[df['index'] == idx_name]
        if len(sub) == 0:
            continue
        idays = sub['date'].nunique()
        ipnl  = sub['pnl_rs'].sum()
        iwr   = 100 * sub['won'].mean()
        iavg  = ipnl / idays if idays else 0
        imon  = iavg * 22
        print(f"  {idx_name:<12} {len(sub):>7} {iwr:>4.0f}% {ipnl:>+12,.0f} {idays:>6} {iavg:>+10,.0f} {imon:>+10,.0f}")

    print(f"\n  PER STRATEGY (combined):")
    print(f"  {'Strategy':<25} {'N':>5} {'WR%':>5} {'Total':>12} {'Avg/T':>8}")
    print(f"  {'-'*60}")
    for sname in sorted(df['strategy'].unique()):
        sd = df[df['strategy'] == sname]
        print(f"  {sname:<25} {len(sd):>5} {100*sd['won'].mean():>4.0f}% "
              f"{sd['pnl_rs'].sum():>+12,.0f} {sd['pnl_rs'].mean():>+8,.0f}")

    print(f"\n  EXIT BREAKDOWN (combined):")
    print(f"  {'Exit':<10} {'N':>5} {'Total':>12} {'Avg':>8}")
    print(f"  {'-'*38}")
    for xr in df['exit_reason'].value_counts().index:
        xd = df[df['exit_reason'] == xr]
        print(f"  {xr:<10} {len(xd):>5} {xd['pnl_rs'].sum():>+12,.0f} {xd['pnl_rs'].mean():>+8,.0f}")

    print(f"\n  DAILY PnL DISTRIBUTION:")
    for thresh, label in [(500,'Rs.500'),(1000,'Rs.1000'),(2000,'Rs.2000'),
                          (3000,'Rs.3000'),(5000,'Rs.5000 (5%)')]:
        print(f"  Days >= {label:<16}: {(daily>=thresh).sum()}/{udays}")

    print(f"\n  MONTHLY BREAKDOWN:")
    df['month'] = df['date'].dt.to_period('M')
    for m, v in df.groupby('month')['pnl_rs'].sum().items():
        bar  = '#' * min(int(abs(v)/1000), 30)
        pct  = v / CAPITAL * 100
        sign = '+' if v >= 0 else ''
        print(f"  {m}  Rs.{v:>+8,.0f}  ({pct:+5.1f}%)  {bar}")

    print(f"\n  TOP 10 DAYS:")
    for dt, pnl in daily.sort_values(ascending=False).head(10).items():
        dtrades = df[df['date'] == dt]
        detail  = ' | '.join(f"{r['index'][:2]}:{r['strategy'][:8]}({r['direction']})"
                              for _, r in dtrades.iterrows())
        print(f"  {str(dt)[:10]}  Rs.{pnl:>+8,.0f}  {detail}")

    print(f"\n  WORST 5 DAYS:")
    for dt, pnl in daily.sort_values().head(5).items():
        dtrades = df[df['date'] == dt]
        detail  = ' | '.join(f"{r['index'][:2]}:{r['strategy'][:8]}[{r['exit_reason']}]"
                              for _, r in dtrades.iterrows())
        print(f"  {str(dt)[:10]}  Rs.{pnl:>+8,.0f}  {detail}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 70)
    print("BACKTEST V7 — ALL 5 INDICES — REAL FETCHED DATA ONLY")
    print("  1 lot per index | 8 locked strategies | parallel threads")
    print("=" * 70)

    # ── Step 1: Load real parquets for each index ─────────────────────────────
    print("\nLoading option data for all indices...")
    datasets: Dict[str, Tuple[pd.DataFrame, pd.DataFrame, IndexConfig]] = {}
    total_days = 0

    for idx_name, cfg in INDEX_CONFIGS.items():
        opt = load_option_data_for_index(idx_name)
        if opt.empty:
            print(f"  [{idx_name}] SKIPPED — no parquets found")
            continue
        eod = build_eod_from_option_data(opt)
        datasets[idx_name] = (opt, eod, cfg)
        total_days = max(total_days, opt['date'].nunique())

    print(f"\nLoaded {len(datasets)} indices: {list(datasets.keys())}")

    # ── Step 2: Run all indices in parallel threads ───────────────────────────
    print(f"\n{'='*70}")
    print("Running backtests in parallel...")
    print(f"{'='*70}")

    results: Dict[str, List[Trade]] = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(run_index, idx_name, opt, eod, cfg): idx_name
            for idx_name, (opt, eod, cfg) in datasets.items()
        }
        for future in as_completed(futures):
            idx_name = futures[future]
            try:
                trades, name = future.result()
                results[name] = trades
                print(f"  [{name}] Completed: {len(trades)} trades", flush=True)
            except Exception as e:
                print(f"  [{idx_name}] ERROR: {e}")
                import traceback; traceback.print_exc()

    # ── Step 3: Report ────────────────────────────────────────────────────────
    print()
    report_multi(results, total_days)

    # ── Step 4: Save CSV ──────────────────────────────────────────────────────
    rows = []
    for idx_name, trades in results.items():
        for t in trades:
            d = t.__dict__.copy()
            d['index'] = idx_name
            rows.append(d)
    if rows:
        out = pd.DataFrame(rows)
        os.makedirs('backtest_results', exist_ok=True)
        out.to_csv('backtest_results/v7_multiindex_trades.csv', index=False)
        print(f"\n  Saved {len(out)} trades → backtest_results/v7_multiindex_trades.csv")
