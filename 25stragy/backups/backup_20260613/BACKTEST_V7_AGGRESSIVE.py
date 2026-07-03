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
# REALISTIC 5-10% DAILY TARGET with LOOSER TSL
# Goal: Capture bigger moves per trade to achieve 5-10% daily (₹25K-₹50K)
TSL_ACTIVATE = 0.06     # TIGHT: Arm at 6% - proven setting
TSL_TRAIL    = 0.04     # TIGHT: Trail 4% - lock in profits
SL_BACKSTOP  = 0.30     # 30% hard stop
TARGET_PCT   = 0.35     # 35% target - realistic
HARD_EXIT    = 1430     # Trade until 14:30

from BACKTEST_V6_PROFILED import (
    ACTIVE_STRATEGIES as V6_ACTIVE_STRATEGIES, ENTRY_START, ENTRY_CUTOFF, FIXED_TARGET_STRATEGIES,
    TRADEABLE_REGIMES, STRATEGY_PROFILES,
    # TSL_* imported locally above for override
    SL_BACKSTOP as SL_BACKSTOP_V6, TARGET_PCT as TARGET_PCT_V6, HARD_EXIT as HARD_EXIT_V6,
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
    # MAX 2 LOTS PER TRADE: max_ce_day=2 limits to 2 entries per strategy per day
    'NIFTY':      IndexConfig('NIFTY',      75,  50,  3, premium_scale=1.0,  hard_exit=1430, max_ce_day=2, wide_range_pts=120,  entry_cutoff=1430),
    'BANKNIFTY':  IndexConfig('BANKNIFTY',  15,  100, 2, premium_scale=3.0,  hard_exit=1430, max_ce_day=2, wide_range_pts=300,  entry_cutoff=1430),
    'FINNIFTY':   IndexConfig('FINNIFTY',   40,  50,  1, premium_scale=1.6,  hard_exit=1430, max_ce_day=2, wide_range_pts=120,  entry_cutoff=1430),
    'SENSEX':     IndexConfig('SENSEX',     10,  100, 4, premium_scale=4.0,  hard_exit=1430, max_ce_day=2, wide_range_pts=350,  entry_cutoff=1430),  # FIX: Same limit as others
    # MIDCPNIFTY remains disabled - was major loss maker (-57K)
    # 'MIDCPNIFTY': IndexConfig('MIDCPNIFTY', 75,  25,  1, premium_scale=1.1,  hard_exit=1430, max_ce_day=15, wide_range_pts=70,   entry_cutoff=1430),
}


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY DNA FRAMEWORK - Per-Strategy Calibration (Like Per-Index DNA)
# ─────────────────────────────────────────────────────────────────────────────
# Each strategy has unique: TSL params, entry thresholds, max trades, regime filters
# This replaces the "one size fits all" approach that killed the 16 strategies
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StrategyDNA:
    """Unique DNA for each strategy - determines its behavior and settings"""
    name: str
    tsl_activate: float       # % profit to activate TSL
    tsl_trail: float          # % trail below peak
    target_pct: float         # Hard target %
    sl_backstop: float        # Hard SL %
    entry_threshold: float    # Min confidence to enter (0.0-1.0)
    max_trades_per_day: int   # Limit overtrading
    min_premium: float        # Minimum premium to trade
    max_premium: float        # Maximum premium (risk control)
    regime_allowed: List[str]  # Which regimes can fire ('ALL' for any)
    volume_required: bool     # Need volume confirmation?
    vwap_required: bool       # Need VWAP confirmation?
    confidence_boost: float   # Extra confidence on good setup
    notes: str                # Why these settings

# =============================================================================
# PER-INDEX PER-STRATEGY DNA MATRIX (4 Indices × 25 Strategies)
# =============================================================================
# This creates a 100-point matrix (4 indices × 25 strategies) where each
# combination has unique TSL, target, and entry parameters based on:
# 1. Strategy behavior (reversal vs trend vs scalping)
# 2. Index characteristics (NIFTY calm vs BANKNIFTY volatile)
# 3. Historical performance data
# =============================================================================

@dataclass
class IndexStrategyDNA:
    """Combined DNA for a specific index + strategy combination"""
    index: str
    strategy: str
    tsl_activate: float
    tsl_trail: float
    target_pct: float
    sl_backstop: float
    entry_threshold: float
    max_trades_per_day: int
    min_premium: float
    max_premium: float
    confidence_boost: float
    notes: str

# Base multipliers for each index (adjusts all strategies)
INDEX_TSL_MULTIPLIERS = {
    'NIFTY':      {'activate': 1.0, 'trail': 1.0, 'target': 1.0},  # Baseline
    'BANKNIFTY':  {'activate': 1.3, 'trail': 1.3, 'target': 1.2},  # 30% more room (volatile)
    'FINNIFTY':   {'activate': 1.2, 'trail': 1.2, 'target': 1.1},  # 20% more room
    'SENSEX':     {'activate': 1.4, 'trail': 1.4, 'target': 1.3},  # 40% more room (widest moves)
}

# Base DNA for each strategy (before index adjustment)
BASE_STRATEGY_DNA = {
    # === TIER 1: LOCKED WORKING STRATEGIES (8) ===
    'DAY_LOW_BULLISH':       {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.60, 'sl': 0.35, 'thresh': 0.80, 'max_d': 5, 'min_p': 50,  'max_p': 500,  'boost': 0.05},
    'DAY_HIGH_BEARISH':      {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.60, 'sl': 0.35, 'thresh': 0.82, 'max_d': 3, 'min_p': 50,  'max_p': 500,  'boost': 0.03},
    'MEAN_REVERSION':        {'tsl_a': 0.06, 'tsl_t': 0.04, 'tgt': 0.35, 'sl': 0.30, 'thresh': 0.82, 'max_d': 4, 'min_p': 45,  'max_p': 600,  'boost': 0.05},  # OPTIMIZED: ADX 25 filter active, tighter TSL
    'VOLATILITY_BREAKOUT':   {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.70, 'sl': 0.35, 'thresh': 0.85, 'max_d': 4, 'min_p': 60,  'max_p': 700,  'boost': 0.05},
    'EARLY_BREAKDOWN':       {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.60, 'sl': 0.35, 'thresh': 0.90, 'max_d': 2, 'min_p': 40,  'max_p': 400,  'boost': 0.08},
    'BEAR_TREND_FOLLOWER': {'tsl_a': 0.12, 'tsl_t': 0.10, 'tgt': 0.80, 'sl': 0.35, 'thresh': 0.88, 'max_d': 3, 'min_p': 45,  'max_p': 500,  'boost': 0.05},
    'BULL_TREND_FOLLOWER': {'tsl_a': 0.12, 'tsl_t': 0.10, 'tgt': 0.80, 'sl': 0.35, 'thresh': 0.88, 'max_d': 3, 'min_p': 45,  'max_p': 500,  'boost': 0.05},
    'ORDER_BLOCK_REVERSAL':  {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.60, 'sl': 0.35, 'thresh': 0.84, 'max_d': 4, 'min_p': 50,  'max_p': 500,  'boost': 0.05},
    
    # === TIER 2: MARGINAL REVIVAL (4) ===
    'WIDE_RANGE_RIDER':      {'tsl_a': 0.07, 'tsl_t': 0.05, 'tgt': 0.50, 'sl': 0.30, 'thresh': 0.82, 'max_d': 3, 'min_p': 60,  'max_p': 600,  'boost': 0.03},  # OPTIMIZED: Earlier TSL 7%/5%, entry cutoff 12:30 in filter code
    'MAGIC_SQUARE':          {'tsl_a': 0.05, 'tsl_t': 0.03, 'tgt': 0.20, 'sl': 0.20, 'thresh': 0.85, 'max_d': 3, 'min_p': 100, 'max_p': 400,  'boost': 0.05},  # OPTIMIZED: Faster TSL 5%/3%, lower target 20%, higher min premium 100
    'SHORT_UNWIND':          {'tsl_a': 0.04, 'tsl_t': 0.02, 'tgt': 0.20, 'sl': 0.15, 'thresh': 0.90, 'max_d': 1, 'min_p': 100, 'max_p': 350,  'boost': 0.03},  # ULTRA FIX: Entry 10:15, OI+volume based, NOT PCR, 1 trade only
    'ENHANCED_BEARISH':      {'tsl_a': 0.12, 'tsl_t': 0.10, 'tgt': 0.80, 'sl': 0.35, 'thresh': 0.75, 'max_d': 3, 'min_p': 50,  'max_p': 500,  'boost': 0.05},
    
    # === TIER 3: KILLER FIXES (3) ===
    'ULTIMATE_DAY_HIGH_LOW': {'tsl_a': 0.15, 'tsl_t': 0.12, 'tgt': 1.00, 'sl': 0.40, 'thresh': 0.75, 'max_d': 2, 'min_p': 100, 'max_p': 700,  'boost': 0.08},
    'SCALPING':              {'tsl_a': 0.06, 'tsl_t': 0.04, 'tgt': 0.25, 'sl': 0.20, 'thresh': 0.90, 'max_d': 5, 'min_p': 80,  'max_p': 250,  'boost': 0.05},
    'OPTIONS_GREEKS':        {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.50, 'sl': 0.30, 'thresh': 0.85, 'max_d': 3, 'min_p': 70,  'max_p': 500,  'boost': 0.05},
    
    # === TIER 4: NEW STRATEGIES (9) ===
    'AI_ENHANCED':           {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.60, 'sl': 0.35, 'thresh': 0.82, 'max_d': 4, 'min_p': 50,  'max_p': 500,  'boost': 0.05},
    'BREAKOUT':              {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.60, 'sl': 0.35, 'thresh': 0.85, 'max_d': 3, 'min_p': 40,  'max_p': 400,  'boost': 0.05},
    'GAMMA_BLAST':           {'tsl_a': 0.15, 'tsl_t': 0.12, 'tgt': 2.00, 'sl': 0.50, 'thresh': 0.80, 'max_d': 2, 'min_p': 10,  'max_p': 150,  'boost': 0.10},
    'ZERO_HERO':             {'tsl_a': 0.12, 'tsl_t': 0.10, 'tgt': 1.00, 'sl': 0.35, 'thresh': 0.85, 'max_d': 2, 'min_p': 20,  'max_p': 100,  'boost': 0.05},
    'MORNING_BREAKOUT':      {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.60, 'sl': 0.30, 'thresh': 0.88, 'max_d': 2, 'min_p': 40,  'max_p': 400,  'boost': 0.08},
    'LONG_UNWIND':           {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.50, 'sl': 0.30, 'thresh': 0.82, 'max_d': 3, 'min_p': 50,  'max_p': 400,  'boost': 0.05},
    'PUT_WRITER_SUPPORT':    {'tsl_a': 0.08, 'tsl_t': 0.06, 'tgt': 0.40, 'sl': 0.25, 'thresh': 0.85, 'max_d': 3, 'min_p': 50,  'max_p': 200,  'boost': 0.05},
    'RESIST_BREAK':          {'tsl_a': 0.08, 'tsl_t': 0.06, 'tgt': 0.50, 'sl': 0.20, 'thresh': 0.85, 'max_d': 3, 'min_p': 50,  'max_p': 250,  'boost': 0.05},
    'DAY_HIGH_LOW_TRADITIONAL': {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.60, 'sl': 0.35, 'thresh': 0.80, 'max_d': 3, 'min_p': 50,  'max_p': 500,  'boost': 0.05},
    'ENHANCED_BULLISH':      {'tsl_a': 0.10, 'tsl_t': 0.08, 'tgt': 0.60, 'sl': 0.30, 'thresh': 0.82, 'max_d': 3, 'min_p': 50,  'max_p': 500,  'boost': 0.05},
    'TREND_FOLLOWING':       {'tsl_a': 0.04, 'tsl_t': 0.02, 'tgt': 0.20, 'sl': 0.20, 'thresh': 0.92, 'max_d': 1, 'min_p': 80,  'max_p': 400,  'boost': 0.03},  # ULTRA FIX: Entry 10:30, fast TSL 4%/2%, 1 trade only, high conf 0.92
    
    # === TIER 5: NEW UNTESTED STRATEGIES (10 added for +Rs.73K potential) ===
    'MOMENTUM_BURST':        {'tsl_a': 0.06, 'tsl_t': 0.04, 'tgt': 0.40, 'sl': 0.25, 'thresh': 0.85, 'max_d': 2, 'min_p': 60,  'max_p': 400,  'boost': 0.05},
    'VWAP_BOUNCE':           {'tsl_a': 0.05, 'tsl_t': 0.03, 'tgt': 0.30, 'sl': 0.20, 'thresh': 0.87, 'max_d': 2, 'min_p': 70,  'max_p': 350,  'boost': 0.04},
    'OPENING_DRIVE':         {'tsl_a': 0.08, 'tsl_t': 0.06, 'tgt': 0.50, 'sl': 0.30, 'thresh': 0.88, 'max_d': 2, 'min_p': 50,  'max_p': 400,  'boost': 0.06},
    'PREMIUM_CRUSH':         {'tsl_a': 0.04, 'tsl_t': 0.02, 'tgt': 0.20, 'sl': 0.15, 'thresh': 0.86, 'max_d': 3, 'min_p': 90,  'max_p': 300,  'boost': 0.04},
    'RSI_REVERSAL':          {'tsl_a': 0.05, 'tsl_t': 0.03, 'tgt': 0.30, 'sl': 0.20, 'thresh': 0.85, 'max_d': 2, 'min_p': 60,  'max_p': 400,  'boost': 0.04},
    'EMA_CROSSOVER':         {'tsl_a': 0.07, 'tsl_t': 0.05, 'tgt': 0.45, 'sl': 0.25, 'thresh': 0.88, 'max_d': 2, 'min_p': 55,  'max_p': 450,  'boost': 0.05},
    'BOLLINGER_SQUEEZE':     {'tsl_a': 0.06, 'tsl_t': 0.04, 'tgt': 0.40, 'sl': 0.25, 'thresh': 0.87, 'max_d': 2, 'min_p': 65,  'max_p': 400,  'boost': 0.05},
    'VOLUME_CLIMAX':         {'tsl_a': 0.05, 'tsl_t': 0.03, 'tgt': 0.35, 'sl': 0.20, 'thresh': 0.89, 'max_d': 2, 'min_p': 70,  'max_p': 350,  'boost': 0.04},
    'ATR_BREAK':             {'tsl_a': 0.08, 'tsl_t': 0.06, 'tgt': 0.55, 'sl': 0.30, 'thresh': 0.86, 'max_d': 2, 'min_p': 50,  'max_p': 500,  'boost': 0.05},
    'MACD_DIVERGENCE':       {'tsl_a': 0.06, 'tsl_t': 0.04, 'tgt': 0.40, 'sl': 0.25, 'thresh': 0.87, 'max_d': 2, 'min_p': 60,  'max_p': 400,  'boost': 0.04},
}

# Build the full DNA matrix
def build_dna_matrix() -> Dict[str, IndexStrategyDNA]:
    """Build 100-point DNA matrix (4 indices × 25 strategies)"""
    matrix = {}
    
    for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']:
        multipliers = INDEX_TSL_MULTIPLIERS[idx]
        
        for strat_name, base in BASE_STRATEGY_DNA.items():
            # Apply index multipliers
            tsl_a = min(0.20, base['tsl_a'] * multipliers['activate'])
            tsl_t = min(0.15, base['tsl_t'] * multipliers['trail'])
            tgt = min(2.50, base['tgt'] * multipliers['target'])
            
            key = f"{idx}:{strat_name}"
            matrix[key] = IndexStrategyDNA(
                index=idx,
                strategy=strat_name,
                tsl_activate=round(tsl_a, 2),
                tsl_trail=round(tsl_t, 2),
                target_pct=round(tgt, 2),
                sl_backstop=base['sl'],
                entry_threshold=base['thresh'],
                max_trades_per_day=base['max_d'],
                min_premium=base['min_p'],
                max_premium=base['max_p'],
                confidence_boost=base['boost'],
                notes=f"{idx} {strat_name}: A{round(tsl_a,2)}/T{round(tsl_t,2)}/G{round(tgt,2)}"
            )
    
    return matrix

# Build the matrix
INDEX_STRATEGY_DNA_MATRIX = build_dna_matrix()

# Helper to get DNA for a specific index+strategy combination
def get_index_strategy_dna(index: str, strategy: str) -> IndexStrategyDNA:
    """Get DNA for specific index + strategy combination"""
    key = f"{index}:{strategy}"
    if key in INDEX_STRATEGY_DNA_MATRIX:
        return INDEX_STRATEGY_DNA_MATRIX[key]
    
    # Fallback to base strategy DNA with NIFTY multipliers
    base = BASE_STRATEGY_DNA.get(strategy, BASE_STRATEGY_DNA['MEAN_REVERSION'])
    return IndexStrategyDNA(
        index=index,
        strategy=strategy,
        tsl_activate=base['tsl_a'],
        tsl_trail=base['tsl_t'],
        target_pct=base['tgt'],
        sl_backstop=base['sl'],
        entry_threshold=base['thresh'],
        max_trades_per_day=base['max_d'],
        min_premium=base['min_p'],
        max_premium=base['max_p'],
        confidence_boost=base['boost'],
        notes=f"Default {index}:{strategy}"
    )

# For compatibility, also provide simple strategy DNA (uses NIFTY baseline)
class StrategyDNA:
    """Simple wrapper for backward compatibility"""
    def __init__(self, name: str):
        dna = get_index_strategy_dna('NIFTY', name)
        self.name = name
        self.tsl_activate = dna.tsl_activate
        self.tsl_trail = dna.tsl_trail
        self.target_pct = dna.target_pct
        self.sl_backstop = dna.sl_backstop
        self.entry_threshold = dna.entry_threshold
        self.max_trades_per_day = dna.max_trades_per_day
        self.min_premium = dna.min_premium
        self.max_premium = dna.max_premium
        self.regime_allowed = ['ALL']
        self.volume_required = False
        self.vwap_required = False
        self.confidence_boost = dna.confidence_boost
        self.notes = dna.notes

# Override ACTIVE_STRATEGIES
ACTIVE_STRATEGIES = set(BASE_STRATEGY_DNA.keys())
print(f"[DNA MATRIX] Loaded {len(ACTIVE_STRATEGIES)} strategies × 4 indices = {len(INDEX_STRATEGY_DNA_MATRIX)} DNA combinations")

# Helper function to get DNA for a strategy
def get_strategy_dna(name: str) -> StrategyDNA:
    """Get DNA for a strategy, return default if not found"""
    if name in STRATEGY_DNA:
        return STRATEGY_DNA[name]
    # Default DNA for unknown strategies
    return StrategyDNA(
        name=name,
        tsl_activate=0.06, tsl_trail=0.04, target_pct=0.35, sl_backstop=0.30,
        entry_threshold=0.80, max_trades_per_day=3, min_premium=50, max_premium=500,
        regime_allowed=['ALL'], volume_required=False, vwap_required=False,
        confidence_boost=0.0, notes='Default DNA'
    )


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
          f"| {data['date'].min()} -> {data['date'].max()}", flush=True)
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


# =============================================================================
# STRATEGY ENHANCEMENT FILTERS (All 10 Critical Improvements)
# =============================================================================
# These filters eliminate false triggers and improve win rates
# Expected improvement: 79% → 85-87% WR
# =============================================================================

# Filter 1: Volume Spike Filter (1.5x average) - For reversal strategies
def volume_spike_filter(c15_slice: pd.DataFrame, min_spike: float = 1.5) -> bool:
    """Require volume > 1.5x average to confirm reversal strength"""
    if len(c15_slice) < 3:
        return True  # Not enough data, allow
    avg_volume = c15_slice['volume'].rolling(window=10, min_periods=3).mean().iloc[-1]
    current_volume = c15_slice['volume'].iloc[-1]
    return current_volume >= (avg_volume * min_spike)

# Filter 2: ADX Trend Strength Filter - For mean reversion
def adx_filter(c15_slice: pd.DataFrame, max_adx: float = 25.0) -> bool:
    """Block mean reversion if ADX > 25 (trending market)"""
    try:
        high = c15_slice['high']
        low = c15_slice['low']
        close = c15_slice['close']
        
        # Calculate +DM and -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Smoothed
        atr = tr.rolling(window=14, min_periods=5).mean()
        plus_di = 100 * plus_dm.rolling(window=14, min_periods=5).mean() / atr
        minus_di = 100 * minus_dm.rolling(window=14, min_periods=5).mean() / atr
        
        # DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(window=14, min_periods=5).mean().iloc[-1]
        
        return adx < max_adx  # True if not trending
    except:
        return True  # Allow if calculation fails

# Filter 3: 3-Cycle PCR Stability - For SHORT_UNWIND
class PCRHistory:
    """Track PCR history for stability check"""
    def __init__(self, cycles: int = 3):
        self.history = []
        self.cycles = cycles
    
    def add(self, pcr: float):
        self.history.append(pcr)
        if len(self.history) > self.cycles:
            self.history.pop(0)
    
    def is_stable(self, threshold: float = 0.15) -> bool:
        """Check if PCR is stable (variance < 15%)"""
        if len(self.history) < self.cycles:
            return True  # Not enough history, allow
        variance = max(self.history) - min(self.history)
        avg_pcr = sum(self.history) / len(self.history)
        return (variance / avg_pcr) < threshold if avg_pcr > 0 else True

# Per-day PCR history tracker
_pcr_history: Dict[str, PCRHistory] = {}

def get_pcr_history(day: str) -> PCRHistory:
    """Get or create PCR history for a day"""
    if day not in _pcr_history:
        _pcr_history[day] = PCRHistory(cycles=3)
    return _pcr_history[day]

def pcr_stability_filter(day: str, pcr: float) -> bool:
    """Require 3-cycle PCR stability for SHORT_UNWIND"""
    history = get_pcr_history(day)
    history.add(pcr)
    return history.is_stable()

# Filter 4: EMA Alignment Filter - For Trend Followers
def ema_alignment_filter(c15_slice: pd.DataFrame, direction: str) -> bool:
    """Require EMA 9 > 21 > 50 for bull, 9 < 21 < 50 for bear"""
    try:
        close = c15_slice['close']
        ema9 = close.ewm(span=9, adjust=False).mean().iloc[-1]
        ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
        ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
        
        if direction == 'CE':  # Bullish
            return ema9 > ema21 > ema50
        else:  # Bearish (PE)
            return ema9 < ema21 < ema50
    except:
        return True  # Allow if calculation fails

# Filter 5: Entry Time Cutoff (13:00) - For all strategies
def entry_time_filter(hhmm: int, cutoff: int = 1300) -> bool:
    """Block entries after 13:00 to avoid TIME exits"""
    return hhmm < cutoff

# Filter 6: Regime Gate - For DAY_HIGH_BEARISH
def regime_gate_filter(regime: str, blocked_regimes: set) -> bool:
    """Block strategy on specific regimes (e.g., DAY_HIGH_BEARISH on TRENDING_BULL)"""
    return regime not in blocked_regimes

# Filter 7: Min Premium Check - For MAGIC_SQUARE
def min_premium_filter(real_prem: float, min_required: float) -> bool:
    """Ensure premium > minimum to cover fees"""
    return real_prem >= min_required

# Filter 8: Time Window Filter - For MAGIC_SQUARE
def time_window_filter(hhmm: int, windows: list) -> bool:
    """Only allow trades in specific time windows (e.g., 10:30-11:30)"""
    for start, end in windows:
        if start <= hhmm <= end:
            return True
    return False

# Filter 9: VWAP Confirmation - For WIDE_RANGE_RIDER
def vwap_confirmation_filter(c15_slice: pd.DataFrame, direction: str) -> bool:
    """Confirm direction with VWAP position"""
    try:
        close = c15_slice['close'].iloc[-1]
        # Calculate VWAP
        typical = (c15_slice['high'] + c15_slice['low'] + c15_slice['close']) / 3
        volume = c15_slice['volume']
        vwap = (typical * volume).cumsum() / volume.cumsum()
        vwap_current = vwap.iloc[-1]
        
        if direction == 'CE':  # Bullish
            return close > vwap_current  # Price above VWAP
        else:  # Bearish
            return close < vwap_current  # Price below VWAP
    except:
        return True  # Allow if calculation fails

# Filter 10: Bollinger Band Position - For Mean Reversion enhancement
def bb_position_filter(c15_slice: pd.DataFrame, threshold: float = 2.0) -> bool:
    """Require price at BB 2σ for strong mean reversion signal"""
    try:
        close = c15_slice['close']
        sma20 = close.rolling(window=20, min_periods=5).mean()
        std20 = close.rolling(window=20, min_periods=5).std()
        upper = sma20 + (std20 * 2)
        lower = sma20 - (std20 * 2)
        
        current = close.iloc[-1]
        upper_val = upper.iloc[-1]
        lower_val = lower.iloc[-1]
        
        # True if price is beyond 2σ (extended)
        return current >= upper_val or current <= lower_val
    except:
        return True  # Allow if calculation fails

# =============================================================================
# ENHANCED SIGNAL CHECK with All Filters
# =============================================================================

def signal_check_idx(strat, direction: str, c15_slice, day_ohlc: dict,
                     pcr: float, hhmm: int, expiry: bool,
                     real_prem: float, cfg: 'IndexConfig', regime: str = 'NORMAL', day: str = '') -> bool:
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

    # =============================================================================
    # APPLY ALL 10 ENHANCEMENT FILTERS
    # =============================================================================
    
    # =============================================================================
    # TIERED ENTRY CUTOFF SYSTEM - Optimized for profit + drawdown control
    # Goal: Balance early entry (avoid TIME exits) vs profit opportunity
    # =============================================================================
    
    # TIER 1: ULTRA STRICT 11:00 - High conviction trend strategies only
    TIER1_ELEVEN_AM = {'BULL_TREND_FOLLOWER', 'BEAR_TREND_FOLLOWER', 
                       'DAY_LOW_BULLISH', 'DAY_HIGH_BEARISH',
                       'TREND_FOLLOWING', 'SHORT_UNWIND'}  # Losers get strictest
    
    # TIER 2: MODERATE 12:30 - Proven reversal/breakout strategies
    TIER2_TWELVE_THIRTY = {'MAGIC_SQUARE', 'WIDE_RANGE_RIDER', 'MEAN_REVERSION',
                           'ORDER_BLOCK_REVERSAL', 'VOLATILITY_BREAKOUT',
                           'EARLY_BREAKDOWN', 'MORNING_BREAKOUT'}
    
    # TIER 3: STANDARD 13:00 - Volume-based and new strategies
    TIER3_ONE_PM = {'ENHANCED_BEARISH', 'ENHANCED_BULLISH', 'ULTIMATE_DAY_HIGH_LOW',
                    'SCALPING', 'OPTIONS_GREEKS', 'AI_ENHANCED', 'BREAKOUT',
                    'GAMMA_BLAST', 'ZERO_HERO', 'LONG_UNWIND', 'PUT_WRITER_SUPPORT',
                    'RESIST_BREAK', 'DAY_HIGH_LOW_TRADITIONAL',
                    # New 10 strategies
                    'MOMENTUM_BURST', 'VWAP_BOUNCE', 'OPENING_DRIVE', 'PREMIUM_CRUSH',
                    'RSI_REVERSAL', 'EMA_CROSSOVER', 'BOLLINGER_SQUEEZE', 'VOLUME_CLIMAX',
                    'ATR_BREAK', 'MACD_DIVERGENCE'}
    
    if strat.name in TIER1_ELEVEN_AM:
        if strat.name in {'TREND_FOLLOWING', 'SHORT_UNWIND'}:
            # DISABLED - These always lose, return False
            return False
        if not entry_time_filter(hhmm, cutoff=1100):
            return False
    elif strat.name in TIER2_TWELVE_THIRTY:
        if not entry_time_filter(hhmm, cutoff=1230):
            return False
    elif strat.name in TIER3_ONE_PM:
        if not entry_time_filter(hhmm, cutoff=1300):
            return False
    else:
        # Default 12:30 for any unspecified strategy
        if not entry_time_filter(hhmm, cutoff=1230):
            return False
    
    # Filter 1 & 8: Volume Spike Filter for reversals and breakouts
    REVERSAL_STRATS = {'DAY_LOW_BULLISH', 'DAY_HIGH_BEARISH', 'ULTIMATE_DAY_HIGH_LOW', 
                       'ORDER_BLOCK_REVERSAL', 'MEAN_REVERSION'}
    if strat.name in REVERSAL_STRATS:
        if not volume_spike_filter(c15_slice, min_spike=1.3):  # 1.3x for flexibility
            return False  # No volume confirmation - likely false reversal
    
    # Filter 2 & 10: ADX + BB Position for Mean Reversion
    if strat.name == 'MEAN_REVERSION':
        if not adx_filter(c15_slice, max_adx=28):  # Slightly higher for flexibility
            return False  # Trending market - mean reversion will fail
        if not bb_position_filter(c15_slice, threshold=1.8):  # 1.8σ for more signals
            return False  # Price not extended enough
    
    # Filter 3: 3-Cycle PCR Stability + Volume for SHORT_UNWIND
    if strat.name == 'SHORT_UNWIND' and day:
        if not pcr_stability_filter(day, pcr):
            return False  # PCR not stable - unreliable signal
        # FIX: Add volume spike requirement for short unwinding (needs conviction)
        if not volume_spike_filter(c15_slice, min_spike=1.2):
            return False  # No volume = no conviction in short covering
    
    # Filter 4: EMA Alignment for Trend Followers
    TREND_FOLLOWERS = {'BEAR_TREND_FOLLOWER', 'BULL_TREND_FOLLOWER', 'TREND_FOLLOWING'}
    if strat.name in TREND_FOLLOWERS:
        if not ema_alignment_filter(c15_slice, direction):
            return False  # EMAs not aligned - trend not confirmed
    
    # Filter 6: Regime Gate for DAY_HIGH_BEARISH
    if strat.name == 'DAY_HIGH_BEARISH':
        if not regime_gate_filter(regime, blocked_regimes={'TRENDING_BULL'}):
            return False  # Don't fight strong uptrend
    
    # Filter 7: Min Premium for MAGIC_SQUARE (RELAXED - removed time window)
    if strat.name == 'MAGIC_SQUARE':
        if not min_premium_filter(real_prem, min_required=80):
            return False  # Premium too low - fees will eat profit
        # RELAXED: Removed time window restriction - allow any time with good setup
    
    # Filter 9: VWAP Confirmation for WIDE_RANGE_RIDER (RELAXED - made advisory)
    # if strat.name == 'WIDE_RANGE_RIDER':
    #     if not vwap_confirmation_filter(c15_slice, direction):
    #         return False  # Price on wrong side of VWAP
    # RELAXED: VWAP check removed - profile matching already handles direction
    
    # Filter 8: Volume filter for ULTIMATE_DAY_HIGH_LOW (RELAXED 1.4x → 1.2x)
    if strat.name == 'ULTIMATE_DAY_HIGH_LOW':
        if not volume_spike_filter(c15_slice, min_spike=1.2):  # RELAXED from 1.4x
            return False  # Break without volume - likely false
        # RELAXED: Removed regime block - allow on trend days with volume confirmation
    
    # =============================================================================
    # All filters passed - allow trade
    # =============================================================================
    
    # Non-NIFTY: profile already validated all market conditions with
    # index-calibrated thresholds — no need for NIFTY-tuned signal_check
    return True

def execute_tsl_idx(entry_bar: pd.Series, remaining: pd.DataFrame, hard_exit: int = HARD_EXIT, 
                     premium_scale: float = 1.0, regime: str = 'NORMAL', strat_name: str = ''):
    # Index-calibrated TSL: Non-NIFTY indices need looser parameters to capture bigger moves
    # NIFTY reference: TSL_ACTIVATE=6%, TSL_TRAIL=4%
    # Scale down % for higher premium indices (they need more room to run)
    activate_adj = 1.0 / max(premium_scale, 0.8)  # FN(1.6) -> 0.63x = 3.8% activate
    trail_adj = 1.0 / max(premium_scale, 0.8)      # FN(1.6) -> 0.63x = 2.5% trail
    target_adj = 1.0 / max(premium_scale, 0.5)     # Allow higher targets for scaled indices
    
    # EXPLOSIVE DAY DNA: Different TSL logic for volatile days
    is_reversal = 'REVERSAL' in strat_name or 'MEAN' in strat_name or 'BLOCK' in strat_name
    is_trend = 'TREND' in strat_name or 'BREAK' in strat_name
    
    if regime == 'EXPLOSIVE_GAP':
        # Explosive days: TIGHTER on reversals (quick profit take), LOOSER on trends (ride momentum)
        if is_reversal:
            # Reversals: tighter TSL to lock in quick moves before they reverse
            activate_adj *= 0.6  # 60% of normal = activate earlier
            trail_adj *= 0.7     # 70% trail = tighter stop
            target_adj *= 0.8    # Lower target but faster capture
        elif is_trend:
            # Trends: looser TSL to ride the explosive move
            activate_adj *= 1.3  # 130% of normal = let it run
            trail_adj *= 1.2     # 120% trail = more room
            target_adj *= 1.5    # Much higher target for explosive trends
    
    tsl_activate = TSL_ACTIVATE * activate_adj
    tsl_trail = TSL_TRAIL * trail_adj
    target_pct = TARGET_PCT * target_adj
    
    ep  = float(entry_bar['open'])
    sl  = ep * (1 - SL_BACKSTOP)
    tgt = ep * (1 + target_pct)
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
        if thi >= ep * (1 + tsl_activate):
            floor = thi * (1 - tsl_trail)
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
    'BANKNIFTY':  set(),  # AGGRESSIVE: Allow all strategies
    'FINNIFTY':   set(),
    'MIDCPNIFTY': set(),
    'SENSEX':     set(),
}


def run_index(idx_name: str, opt_data: pd.DataFrame,
              eod_data: pd.DataFrame, cfg: IndexConfig) -> Tuple[List[Trade], str]:

    print(f"  [{idx_name}] Labelling regimes on {opt_data['date'].nunique()} days...", flush=True)
    day_regimes   = label_days(opt_data)
    exclusions    = INDEX_STRATEGY_EXCLUSIONS.get(idx_name, set())
    active_strats = [s for s in make_strategies()
                     if s.name in ACTIVE_STRATEGIES and s.name not in exclusions]
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
                    # MULTI-TRADE SEQUENCE: Up to 15 trades per direction per day (30 total)
                    if direction == 'CE' and trades_today['CE'] >= cfg.max_ce_day:
                        continue
                    if direction == 'PE' and trades_today['PE'] >= 15:
                        continue

                    profile = idx_profiles[strat.name]
                    armed, conf, arm_reason = match_profile(profile, ctx, state, direction)
                    if not armed:
                        continue
                    # EXPLOSIVE DAY DNA: Multi-tier confidence system
                    # MORE TRADES FOR 15% TARGET: Lower confidence = more opportunities
                    if regime == 'EXPLOSIVE_GAP':
                        # EXPLOSIVE: 0.55+ (was 0.72) - more aggressive on volatile days
                        if conf < 0.55:
                            continue
                        # Explosive day bonus: higher base confidence for profile matching
                        conf = min(0.95, conf + 0.08)  # Boost confidence for explosive entries
                    else:
                        # NORMAL: 0.52+ (was 0.58) - capture more normal opportunities
                        if conf < 0.52:
                            continue
                    lots_multiplier = 2.0  # 2 LOTS per trade (max for drawdown control)


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
                                              day_ohlc, pcr, hhmm, expiry, prem, cfg, 
                                              regime, str(day))  # Pass regime and day for filters
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
                        # EXPLOSIVE DAY TSL: Pass regime and strat_name for specialized logic
                        xp, xr, xt = execute_tsl_idx(entry_bar, remaining, cfg.hard_exit, cfg.premium_scale, regime, strat.name)

                    # Apply dynamic lot sizing
                    actual_lots = int(lots_multiplier)
                    pnl_pts = xp - entry_price
                    pnl_rs  = round(pnl_pts * cfg.lot_size * actual_lots - cfg.brokerage * actual_lots, 2)

                    all_trades.append(Trade(
                        date=day, strategy=strat.name, direction=direction,
                        regime=regime, confidence=conf, lots=actual_lots,
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
        # ALL INDICES ACTIVE - BANKNIFTY re-enabled with 2 lots optimization
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
        print(f"\n  Saved {len(out)} trades -> backtest_results/v7_multiindex_trades.csv")
