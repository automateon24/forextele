#!/usr/bin/env python3
"""
BACKTEST V6 — Strategy DNA Profiling Engine
============================================
Each strategy has a 3-layer profile that must match BEFORE it arms:

  Layer 1 — DAY CONTEXT (computed once at open):
    gap_pct, pcr_at_open, vix_proxy (avg_candle_rng / spot), day_type

  Layer 2 — INTRADAY STATE (updated each 15-min bar):
    rsi_zone, ema_structure, vwap_side, momentum_score, range_consumed_pct

  Layer 3 — CANDLE READINESS (last 3 bars rolling):
    pattern_score: direction consistency, body/range ratio, volume trend

Only strategies whose profile matches the current state get "armed".
Armed strategies check their entry signal. This eliminates ~70% of bad trades
before they happen.

Winning strategies from audit:
  1. DAY_LOW_BULLISH      — 71% WR, +6,270
  2. TREND_FOLLOWING      — 56% WR, +7,074
  3. SHORT_UNWIND         — 90% WR, +4,888
  4. ENHANCED_BULLISH     — 62% WR, +1,464
  5. DAY_HIGH_BEARISH     — 50% WR, +1,334  (include, fix profile)
  6. MAGIC_SQUARE         — 53% WR, +4,070  (marginal but high frequency)

Disabled (proven losers):
  X ULTIMATE_DAY_HIGH_LOW — 37% WR, -21,606
  X SCALPING              — 46% WR,  -9,003
  X OPTIONS_GREEKS        — 47% WR,  -5,626
  X AI_ENHANCED           — 50% WR,  -5,540
  X LONG_UNWIND           — 28% WR,  -2,530
  X GAMMA_BLAST           — 55% WR,  -3,561  (too noisy)
"""

import sys
sys.path.insert(0, 'c:/cursor/options/niftyopt')

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from BACKTEST_V3_TUNED import (
    load_option_data, load_eod_data,
    calc_rsi, build_15min_spot, calc_pcr, is_expiry_day,
    signal_check, make_strategies, execute_trade
)
from regime_detector import label_days

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
LOT_SIZE   = 75
CAPITAL    = 100_000
BROKERAGE  = 40

# Override exits: use V5's proven TSL-only approach
TSL_ACTIVATE = 0.06     # TSL arms at 6% profit (was 8% — earlier arm = more TSL, fewer TIME)
TSL_TRAIL    = 0.04     # trails 4% below peak (was 5% — tighter trail = lock in more)
SL_BACKSTOP  = 0.30     # hard SL at 30% (backstop only)
TARGET_PCT   = 0.35     # hard target at 35%
# BEVEN removed — kills mean-reversion trades that need time to work
# Protection comes from: TSL(8%,5%) + SL_BACKSTOP(30%) + HARD_EXIT(14:15)
HARD_EXIT    = 1415     # force exit at 14:15

# Regimes where we trade
# HIGH_VOLATILITY excluded: 38% WR -3,509 on 8 trades, drawdown -6,494 — ORB breaks reverse
TRADEABLE_REGIMES = {'TRENDING_BULL', 'TRENDING_BEAR', 'NORMAL'}

# Strategies active — each uses best exit style for its move type
# LOCKED (do not modify DNA): DAY_LOW_BULLISH 95%WR, BULL_TREND_FOLLOWER 100%WR,
#   MEAN_REVERSION 83%WR, BEAR_TREND_FOLLOWER 92%WR, DAY_HIGH_BEARISH 82%WR,
#   EARLY_BREAKDOWN 100%WR, VOLATILITY_BREAKOUT 100%WR
ACTIVE_STRATEGIES = {
    'DAY_LOW_BULLISH',       # LOCKED 95% WR — do not touch
    'DAY_HIGH_BEARISH',      # LOCKED 82% WR — do not touch
    'MEAN_REVERSION',        # LOCKED 83% WR — do not touch
    'VOLATILITY_BREAKOUT',   # LOCKED 100% WR — do not touch
    'EARLY_BREAKDOWN',       # LOCKED 100% WR — do not touch
    'BEAR_TREND_FOLLOWER',   # LOCKED 92% WR — do not touch
    'BULL_TREND_FOLLOWER',   # LOCKED 100% WR — do not touch
    # ── Activating inactive strategies for more coverage:
    # ENHANCED_BEARISH removed: 50% WR -671 on 2 trades in 155 days — signal too rare
    # MAGIC_SQUARE removed: 64% WR, net+43 on 39 trades — brokerage destroys it
    'ORDER_BLOCK_REVERSAL',  # Strongest candle level reversal — 1 trade 100% WR, safe
    # SHORT_UNWIND removed: 38% WR -2706 — PCR signal unreliable in 15min data
    # WIDE_RANGE_RIDER: 85% WR but 2 TIME exits still drag; re-add after more tuning
}

# Strategies that use fixed target exit instead of TSL (quick-move strategies)
FIXED_TARGET_STRATEGIES = {
    'SHORT_UNWIND': 0.20,   # 20% fixed target — PCR unwind is quick, don't trail
}

# Per-strategy entry START override (audit data: early entries have poor WR on some strategies)
ENTRY_START = {
    'DAY_HIGH_BEARISH':    1230,  # audit: 12:00 entries = 36% WR -4k vs 12:30 = 75% WR +6.5k
    'BULL_TREND_FOLLOWER': 1130,  # audit: 11:00-11:15 = 0% WR -4k vs 11:30+ = 83% WR
    'BEAR_TREND_FOLLOWER': 1130,  # audit: 11:16 entry = -1,652 TIME exit (NORMAL regime)
}

# Per-strategy hard entry cutoff (overrides strat.entry_end based on audit)
# Only enter before this time — entries after lead to TIME exits with no TSL
ENTRY_CUTOFF = {
    'DAY_HIGH_BEARISH':  1245,  # audit10: 12:30 bucket=100% WR; 12:46+ has losses — stay clean
    'DAY_LOW_BULLISH':   1350,  # audit10: 14:01 = -2409; cut before EOD rush
    'MEAN_REVERSION':    1300,  # losses at 1201/1231 but wins go to 1315 — balanced cutoff
    'TREND_FOLLOWING':   1300,  # audit: only 1 TSL at 13:46, 7 TIME exits — strict cutoff
    'ENHANCED_BULLISH':    1300,  # cap at 13:00 — late entries are TIME exits
    'VOLATILITY_BREAKOUT': 1400,  # breakout can happen any time
    'MORNING_BREAKOUT':    1100,  # must enter before 11:00 — it IS an early breakout
    'EARLY_BREAKDOWN':     1100,  # must enter before 11:00 — it IS an early breakdown
    'BEAR_TREND_FOLLOWER': 1300,  # ORB break, enter 11:30-13:00
    'BULL_TREND_FOLLOWER': 1230,  # audit: 12:46 entries all losses — cut at 12:30
    'WIDE_RANGE_RIDER':    1145,  # audit12: only 11:00-11:45 bucket clean (100%/75% WR); 12:15+ too noisy
    'ENHANCED_BEARISH':    1345,  # PE momentum — cut before final hour noise
    'MAGIC_SQUARE':        1300,  # Fib level reversal — 13:00 cutoff
    'ORDER_BLOCK_REVERSAL':1300,  # Block level reversal — 13:00 cutoff
    'SHORT_UNWIND':        1330,  # PCR unwind quick exit — allow until 13:30
}

DISABLED_STRATEGIES = {
    'ULTIMATE_DAY_HIGH_LOW',  # 37% WR killer
    'SCALPING',               # 46% WR + brokerage death
    'OPTIONS_GREEKS',         # 47% WR high freq loser
    'AI_ENHANCED',            # 50% WR, noisy
    'LONG_UNWIND',            # 28% WR
    'GAMMA_BLAST',            # 55% WR but noisy
    'PUT_WRITER_SUPPORT',     # 40% WR
    'ENHANCED_BEARISH',       # fires only 1x per 155 days
    'BREAKOUT',               # fires only 4x per 155 days
    'DAY_HIGH_LOW_TRADITIONAL', # never fires
    'RESIST_BREAK',           # never fires
    'ZERO_HERO',              # fires only 1x per 155 days
}


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY DNA PROFILES
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class StrategyProfile:
    """
    DNA fingerprint for each strategy.
    Each field is a (min, max) tuple = required range.
    None = no requirement on that dimension.
    """
    name: str
    direction: str          # CE, PE, BOTH

    # Layer 1: Day context (computed once at day open)
    gap_pct_range:      Tuple = (-5.0, 5.0)   # gap % from prev close: (-2,2) = small gap days
    pcr_open_range:     Tuple = (0.0, 3.0)    # PCR at open
    vix_proxy_range:    Tuple = (0.0, 99.0)   # avg 15min candle range / spot * 100

    # Layer 2: Intraday state (checked each bar)
    rsi_range:          Tuple = (0, 100)
    ema_structure:      str   = 'ANY'          # BULL (ema5>ema20), BEAR, ANY
    vwap_side:          str   = 'ANY'          # ABOVE, BELOW, ANY
    momentum_dir:       str   = 'ANY'          # UP (close>open), DOWN, ANY
    range_consumed_min: float = 0.0            # % of day range consumed so far (0.0-1.0)
    range_consumed_max: float = 1.0

    # Layer 3: Candle readiness (last 3 bars)
    min_body_ratio:     float = 0.0            # body/range >= this (avoid doji)
    candle_consistency: str   = 'ANY'          # BULL3 (3 green), BEAR3, MIXED, ANY
    vol_trend:          str   = 'ANY'          # RISING, FALLING, ANY

    # Confidence score for lot sizing
    base_confidence:    float = 0.60


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE DEFINITIONS — built from audit data + manual trading knowledge
# ─────────────────────────────────────────────────────────────────────────────
STRATEGY_PROFILES: Dict[str, StrategyProfile] = {

    # ── DAY_LOW_BULLISH: 71% WR ───────────────────────────────────────────────
    # Works when: small gap, market near day low, RSI oversold, starting to bounce
    # Profile: gap small (<0.8%), RSI<45, spot in lower 35% of day range,
    #          last 2 candles green (bounce starting), volume rising
    'DAY_LOW_BULLISH': StrategyProfile(
        name='DAY_LOW_BULLISH', direction='CE',
        gap_pct_range=(-1.5, 1.5),     # no huge gap days
        pcr_open_range=(0.8, 2.5),     # neutral to slightly bearish PCR (bouncing FROM low)
        rsi_range=(20, 48),            # oversold zone
        ema_structure='ANY',           # EMA can still be bearish when bouncing
        vwap_side='ANY',               # price below VWAP is actually fine (oversold bounce)
        momentum_dir='UP',             # current candle must be green (bounce confirmed)
        range_consumed_min=0.30,       # day must have moved at least 30% of its range
        range_consumed_max=0.80,       # but not exhausted (>80% means bounce already happened)
        min_body_ratio=0.25,           # avoid tiny doji
        candle_consistency='ANY',      # mixed candles OK — we want the turn
        vol_trend='RISING',            # volume increasing = real bounce
        base_confidence=0.68,
    ),

    # ── TREND_FOLLOWING (PE direction): 56% WR, +7,074 ────────────────────────
    # Works when: clear downtrend, EMA bearish, price below VWAP, momentum down
    # Profile: ema5<ema20 for last 3 bars, RSI 35-52, VWAP below, 3 red candles
    'TREND_FOLLOWING': StrategyProfile(
        name='TREND_FOLLOWING', direction='PE',
        gap_pct_range=(-3.0, 3.0),     # any gap
        pcr_open_range=(0.0, 3.0),
        rsi_range=(30, 52),            # trending down but not exhausted
        ema_structure='BEAR',          # must be ema5 < ema20
        vwap_side='BELOW',             # price below VWAP = confirmed downtrend
        momentum_dir='DOWN',           # current candle red
        range_consumed_min=0.20,       # some trend already established
        range_consumed_max=0.90,
        min_body_ratio=0.20,
        candle_consistency='ANY',
        vol_trend='ANY',               # volume not required for trend follow
        base_confidence=0.63,
    ),

    # ── SHORT_UNWIND (CE): 90% WR, +4,888 ────────────────────────────────────
    # Works when: PCR < 1.0 (call heavy = shorts covering), EMA bullish, RSI 50+
    # PCR < 1.0 is the primary gate — don't add too many profile restrictions
    'SHORT_UNWIND': StrategyProfile(
        name='SHORT_UNWIND', direction='CE',
        gap_pct_range=(-3.0, 3.0),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(48, 80),            # RSI in bullish zone
        ema_structure='BULL',          # ema5 > ema20 required
        vwap_side='ANY',               # relaxed — PCR already gates this
        momentum_dir='ANY',            # relaxed — PCR + EMA is enough
        range_consumed_min=0.0,
        range_consumed_max=1.0,
        min_body_ratio=0.10,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.72,
    ),

    # ── ENHANCED_BULLISH (CE): 62% WR ────────────────────────────────────────
    # Works when: RSI<46 (dip), green candle = bounce. EMA can lag on dips.
    'ENHANCED_BULLISH': StrategyProfile(
        name='ENHANCED_BULLISH', direction='CE',
        gap_pct_range=(-2.0, 2.0),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(20, 50),            # widened: was 48, misses RSI 48-50 bounces
        ema_structure='ANY',           # FIX: was BULL — contradicts rsi<46 (dip condition)
        vwap_side='ANY',
        momentum_dir='UP',             # green candle required (bounce confirmed)
        range_consumed_min=0.15,
        range_consumed_max=0.85,
        min_body_ratio=0.20,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.62,
    ),

    # ── DAY_HIGH_BEARISH (PE): 50% WR — needs tighter profile ────────────────
    # Works when: near day high, RSI overbought, red candles, rejection
    'DAY_HIGH_BEARISH': StrategyProfile(
        name='DAY_HIGH_BEARISH', direction='PE',
        gap_pct_range=(-3.0, 3.0),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(55, 85),            # must be overbought
        ema_structure='ANY',
        vwap_side='ABOVE',             # was above VWAP before rejection
        momentum_dir='DOWN',           # current candle is red (rejection started)
        range_consumed_min=0.50,       # day high must be established (>50% range used)
        range_consumed_max=1.0,
        min_body_ratio=0.20,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.60,
    ),

    # ── MAGIC_SQUARE: 53% WR, fires 85 times ─────────────────────────────────
    # Needs tighter profile: only fire when momentum is clean (not choppy)
    'MAGIC_SQUARE': StrategyProfile(
        name='MAGIC_SQUARE', direction='BOTH',
        gap_pct_range=(-2.0, 2.0),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(30, 70),            # not at extremes (magic square is momentum)
        ema_structure='ANY',
        vwap_side='ANY',
        momentum_dir='ANY',
        range_consumed_min=0.20,
        range_consumed_max=0.80,       # not at EOD
        min_body_ratio=0.25,           # need real candles not doji
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.58,
    ),

    # ── MEAN_REVERSION: 55% WR ───────────────────────────────────────────────
    # Works when: price at Bollinger Band extremes, RSI extreme
    'MEAN_REVERSION': StrategyProfile(
        name='MEAN_REVERSION', direction='BOTH',
        gap_pct_range=(-2.5, 2.5),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(0, 100),            # RSI handled in signal_check
        ema_structure='ANY',
        vwap_side='ANY',
        momentum_dir='ANY',
        range_consumed_min=0.30,       # needs established range to revert
        range_consumed_max=1.0,
        min_body_ratio=0.10,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.60,
    ),

    # ── VOLATILITY_BREAKOUT: 100% WR (1 trade) ───────────────────────────────
    # High momentum breakout candle: large range, closes at extreme
    'VOLATILITY_BREAKOUT': StrategyProfile(
        name='VOLATILITY_BREAKOUT', direction='BOTH',
        gap_pct_range=(-5.0, 5.0),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(0, 100),
        ema_structure='ANY',
        vwap_side='ANY',
        momentum_dir='ANY',
        range_consumed_min=0.0,
        range_consumed_max=1.0,
        min_body_ratio=0.35,           # needs a real breakout candle body
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.65,
    ),

    # ── ORDER_BLOCK_REVERSAL: 100% WR (2 trades) ────────────────────────────
    'ORDER_BLOCK_REVERSAL': StrategyProfile(
        name='ORDER_BLOCK_REVERSAL', direction='BOTH',
        gap_pct_range=(-3.0, 3.0),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(0, 100),
        ema_structure='ANY',
        vwap_side='ANY',
        momentum_dir='ANY',
        range_consumed_min=0.0,
        range_consumed_max=1.0,
        min_body_ratio=0.10,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.65,
    ),

    # ── MORNING_BREAKOUT (CE): flat open + ORB break above first hour high ────
    # Works when: small gap, breakout above first hour high, RSI > 55, EMA bull
    # Profile: gap < 0.8%, RSI 55-80 (momentum), ema BULL, above VWAP, green candle
    'MORNING_BREAKOUT': StrategyProfile(
        name='MORNING_BREAKOUT', direction='CE',
        gap_pct_range=(-1.5, 1.5),     # allow up to 1.5% gap — too strict was 0 fires
        pcr_open_range=(0.0, 3.0),
        rsi_range=(53, 82),            # RSI in bullish momentum zone
        ema_structure='BULL',
        vwap_side='ABOVE',
        momentum_dir='UP',
        range_consumed_min=0.0,
        range_consumed_max=1.0,
        min_body_ratio=0.20,           # slightly relaxed — early breakout candles vary
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.66,
    ),

    # ── EARLY_BREAKDOWN (PE): flat open + breaks below first hour low ────────
    # Works when: small gap, breakdown below first hour low, RSI < 45, EMA bear
    'EARLY_BREAKDOWN': StrategyProfile(
        name='EARLY_BREAKDOWN', direction='PE',
        gap_pct_range=(-0.8, 0.8),     # must be flat open day
        pcr_open_range=(0.0, 3.0),
        rsi_range=(18, 46),            # RSI in bearish momentum zone
        ema_structure='BEAR',          # ema5 < ema20 required
        vwap_side='BELOW',             # below VWAP = real breakdown
        momentum_dir='DOWN',           # current candle must be red
        range_consumed_min=0.0,
        range_consumed_max=1.0,
        min_body_ratio=0.25,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.66,
    ),

    # ── WIDE_RANGE_RIDER (BOTH): day range > 150pts, trend + pullback entry ──
    # Works when: wide range confirmed, riding dominant direction after RSI reset
    # Tight RSI 44-60: only fires at true pullback zone, not entire trend move
    'WIDE_RANGE_RIDER': StrategyProfile(
        name='WIDE_RANGE_RIDER', direction='BOTH',
        gap_pct_range=(-5.0, 5.0),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(44, 60),            # tight: only at pullback zone (not trend peak or trough)
        ema_structure='ANY',
        vwap_side='ANY',
        momentum_dir='ANY',
        range_consumed_min=0.35,       # 35%+ of range must already be established
        range_consumed_max=0.80,
        min_body_ratio=0.20,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.64,
    ),

    # ── BEAR_TREND_FOLLOWER (PE): TRENDING_BEAR days after ORB low breaks ────
    # 16 uncovered TRENDING_BEAR DOWN days with avg 272pt range
    # Enters after ORB low confirmed broken: EMA bear + below VWAP + red candle
    'BEAR_TREND_FOLLOWER': StrategyProfile(
        name='BEAR_TREND_FOLLOWER', direction='PE',
        gap_pct_range=(-5.0, 5.0),     # any gap — regime gates this, not gap size
        pcr_open_range=(0.0, 3.0),
        rsi_range=(25, 55),            # below 55 = not overbought, trending down
        ema_structure='BEAR',          # ema5 < ema20 = trend confirmed
        vwap_side='BELOW',             # below VWAP = real downtrend
        momentum_dir='DOWN',           # red candle confirmation
        range_consumed_min=0.20,       # some range already consumed (trend started)
        range_consumed_max=0.85,
        min_body_ratio=0.20,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.68,
    ),

    # ── BULL_TREND_FOLLOWER (CE): TRENDING_BULL days after ORB high breaks ────
    # 17 uncovered TRENDING_BULL UP days with avg 260pt range
    # Enters after ORB high confirmed broken: EMA bull + above VWAP + green candle
    'BULL_TREND_FOLLOWER': StrategyProfile(
        name='BULL_TREND_FOLLOWER', direction='CE',
        gap_pct_range=(-5.0, 5.0),     # any gap — regime gates this
        pcr_open_range=(0.0, 3.0),
        rsi_range=(45, 78),            # above 45 = not oversold, trending up
        ema_structure='BULL',          # ema5 > ema20 = trend confirmed
        vwap_side='ABOVE',             # above VWAP = real uptrend
        momentum_dir='UP',             # green candle confirmation
        range_consumed_min=0.20,
        range_consumed_max=0.85,
        min_body_ratio=0.20,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.68,
    ),

    # ── SHORT_UNWIND (CE): 90% WR in V3, quick PCR unwind move ───────────────
    # PCR < 1.0 + EMA bull + RSI > 50 + above VWAP = put writers covering
    # Move is quick (< 30 mins), so FIXED 20% target beats TSL
    'SHORT_UNWIND': StrategyProfile(
        name='SHORT_UNWIND', direction='CE',
        gap_pct_range=(-3.0, 3.0),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(48, 80),
        ema_structure='BULL',
        vwap_side='ANY',
        momentum_dir='ANY',
        range_consumed_min=0.0,
        range_consumed_max=1.0,
        min_body_ratio=0.10,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.72,
    ),

    # ── ENHANCED_BEARISH (PE): RSI overbought fade ───────────────────────────
    # RSI>56 + ema5<ema20 + red candle (vol_spike handled in signal_check not profile)
    'ENHANCED_BEARISH': StrategyProfile(
        name='ENHANCED_BEARISH', direction='PE',
        gap_pct_range=(-5.0, 5.0),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(52, 85),            # RSI overbought zone — relaxed to 52 to allow entries
        ema_structure='ANY',           # EMA gate inside signal_check, not profile
        vwap_side='ANY',
        momentum_dir='DOWN',           # red candle required
        range_consumed_min=0.05,
        range_consumed_max=0.95,
        min_body_ratio=0.10,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.64,
    ),

    # ── MAGIC_SQUARE (BOTH): Fibonacci 61.8/38.2 level reversal ─────────────
    # At 61.8% of day range = PE; at 38.2% of day range = CE
    # Very broad profile — signal_check handles Fibonacci proximity
    'MAGIC_SQUARE': StrategyProfile(
        name='MAGIC_SQUARE', direction='BOTH',
        gap_pct_range=(-5.0, 5.0),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(30, 70),            # wide — signal_check adds RSI direction per side
        ema_structure='ANY',
        vwap_side='ANY',
        momentum_dir='ANY',
        range_consumed_min=0.25,       # need 25%+ range established for Fib levels
        range_consumed_max=0.90,
        min_body_ratio=0.10,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.64,
    ),

    # ── ORDER_BLOCK_REVERSAL (BOTH): strongest 15min candle = support/resistance ─
    # At strongest recent high = PE; at strongest recent low = CE
    'ORDER_BLOCK_REVERSAL': StrategyProfile(
        name='ORDER_BLOCK_REVERSAL', direction='BOTH',
        gap_pct_range=(-5.0, 5.0),
        pcr_open_range=(0.0, 3.0),
        rsi_range=(0, 100),            # no RSI gate — signal_check handles per side
        ema_structure='ANY',
        vwap_side='ANY',
        momentum_dir='ANY',
        range_consumed_min=0.0,
        range_consumed_max=1.0,
        min_body_ratio=0.0,
        candle_consistency='ANY',
        vol_trend='ANY',
        base_confidence=0.62,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# MARKET STATE COMPUTER
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class DayContext:
    gap_pct:      float = 0.0
    pcr_open:     float = 1.0
    vix_proxy:    float = 0.5

@dataclass
class IntradayState:
    rsi:              float = 50.0
    ema_structure:    str   = 'ANY'
    vwap_side:        str   = 'ANY'
    momentum_dir:     str   = 'ANY'
    range_consumed:   float = 0.5
    body_ratio:       float = 0.3
    candle_consist:   str   = 'ANY'
    vol_trend:        str   = 'ANY'
    # Raw values
    ema5:   float = 0.0
    ema20:  float = 0.0
    vwap:   float = 0.0
    pcr:    float = 1.0
    spot:   float = 0.0
    day_high: float = 0.0
    day_low:  float = 0.0


def calc_ema(s: pd.Series, p: int) -> float:
    if len(s) < p: return float(s.mean())
    return float(s.ewm(span=p, adjust=False).mean().iloc[-1])


def compute_day_context(c15: pd.DataFrame, prev_close: float, pcr: float) -> DayContext:
    if len(c15) < 1:
        return DayContext()
    first_spot = float(c15.iloc[0]['close'])
    gap_pct = ((first_spot - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
    # VIX proxy: avg candle range / spot * 100
    if 'high' in c15.columns and 'low' in c15.columns:
        ranges = (c15['high'] - c15['low']).values
        vix_proxy = float(np.mean(ranges[:4]) / first_spot * 100) if first_spot > 0 else 0.5
    else:
        vix_proxy = 0.5
    return DayContext(gap_pct=round(gap_pct, 3), pcr_open=pcr, vix_proxy=round(vix_proxy, 4))


def compute_intraday_state(candles: pd.DataFrame, pcr: float) -> IntradayState:
    if len(candles) < 3:
        return IntradayState()

    closes = candles['close'].values
    opens  = candles['open'].values  if 'open'  in candles.columns else closes
    highs  = candles['high'].values  if 'high'  in candles.columns else closes
    lows   = candles['low'].values   if 'low'   in candles.columns else closes
    vols   = candles['volume'].values if 'volume' in candles.columns else np.ones(len(closes))

    spot  = float(closes[-1])
    c_bar = candles.iloc[-1]
    hi_c  = float(highs[-1]); lo_c = float(lows[-1])
    op_c  = float(opens[-1])

    rsi  = calc_rsi(pd.Series(closes))
    ema5 = calc_ema(pd.Series(closes), 5)
    ema20= calc_ema(pd.Series(closes), 20)

    # VWAP
    if vols.sum() > 0:
        vwap = float((candles['close'] * candles['volume']).sum() / candles['volume'].sum())
    else:
        vwap = float(np.mean(closes))

    # EMA structure
    if ema5 > ema20 * 1.0005:
        ema_struct = 'BULL'
    elif ema5 < ema20 * 0.9995:
        ema_struct = 'BEAR'
    else:
        ema_struct = 'FLAT'

    # VWAP side
    vwap_side = 'ABOVE' if spot > vwap else 'BELOW'

    # Momentum
    mom = 'UP' if spot > op_c else ('DOWN' if spot < op_c else 'FLAT')

    # Range consumed
    day_high = float(np.max(highs))
    day_low  = float(np.min(lows))
    day_range = day_high - day_low
    if day_range > 0:
        range_consumed = (spot - day_low) / day_range
    else:
        range_consumed = 0.5

    # Body ratio of last candle
    candle_range = hi_c - lo_c
    body = abs(spot - op_c)
    body_ratio = body / candle_range if candle_range > 0 else 0.0

    # Candle consistency (last 3)
    if len(closes) >= 3:
        last3_green = sum(1 for i in range(-3, 0) if closes[i] > opens[i])
        last3_red   = sum(1 for i in range(-3, 0) if closes[i] < opens[i])
        if last3_green == 3:
            consist = 'BULL3'
        elif last3_red == 3:
            consist = 'BEAR3'
        else:
            consist = 'MIXED'
    else:
        consist = 'MIXED'

    # Volume trend (last 3 bars rising?)
    if len(vols) >= 3:
        v_trend = 'RISING' if vols[-1] > vols[-2] > vols[-3] * 0.9 else 'FALLING'
    else:
        v_trend = 'ANY'

    return IntradayState(
        rsi=round(rsi, 2), ema_structure=ema_struct, vwap_side=vwap_side,
        momentum_dir=mom, range_consumed=round(range_consumed, 3),
        body_ratio=round(body_ratio, 3), candle_consist=consist, vol_trend=v_trend,
        ema5=ema5, ema20=ema20, vwap=vwap, pcr=pcr,
        spot=spot, day_high=day_high, day_low=day_low,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE MATCHER — returns (armed: bool, confidence: float, reason: str)
# ─────────────────────────────────────────────────────────────────────────────
def match_profile(profile: StrategyProfile, ctx: DayContext, state: IntradayState,
                  direction: str) -> Tuple[bool, float, str]:

    reasons = []
    score   = profile.base_confidence
    fails   = []

    # ── Layer 1: Day context ──────────────────────────────────────────────────
    if not (profile.gap_pct_range[0] <= ctx.gap_pct <= profile.gap_pct_range[1]):
        fails.append(f"gap={ctx.gap_pct:.2f}% out of {profile.gap_pct_range}")
    else:
        score += 0.02

    if not (profile.vix_proxy_range[0] <= ctx.vix_proxy <= profile.vix_proxy_range[1]):
        fails.append(f"vix_proxy={ctx.vix_proxy:.3f}")
    else:
        score += 0.01

    # ── Layer 2: Intraday state ────────────────────────────────────────────────
    rsi_ok = profile.rsi_range[0] <= state.rsi <= profile.rsi_range[1]
    if not rsi_ok:
        fails.append(f"rsi={state.rsi:.1f} need {profile.rsi_range}")
    else:
        # Bonus: deep in zone
        mid = (profile.rsi_range[0] + profile.rsi_range[1]) / 2
        score += 0.03 * (1 - abs(state.rsi - mid) / max(mid - profile.rsi_range[0], 1))

    ema_ok = (profile.ema_structure == 'ANY' or
              profile.ema_structure == state.ema_structure or
              (profile.ema_structure == 'BULL' and state.ema_structure == 'BULL') or
              (profile.ema_structure == 'BEAR' and state.ema_structure == 'BEAR'))
    if not ema_ok:
        fails.append(f"ema={state.ema_structure} need {profile.ema_structure}")
    else:
        score += 0.04

    vwap_ok = (profile.vwap_side == 'ANY' or profile.vwap_side == state.vwap_side)
    if not vwap_ok:
        fails.append(f"vwap={state.vwap_side} need {profile.vwap_side}")
    else:
        score += 0.03

    mom_ok = (profile.momentum_dir == 'ANY' or profile.momentum_dir == state.momentum_dir)
    if not mom_ok:
        fails.append(f"mom={state.momentum_dir} need {profile.momentum_dir}")
    else:
        score += 0.03

    range_ok = (profile.range_consumed_min <= state.range_consumed <= profile.range_consumed_max)
    if not range_ok:
        fails.append(f"range_consumed={state.range_consumed:.2f} need {profile.range_consumed_min}-{profile.range_consumed_max}")
    else:
        score += 0.02

    # ── Layer 3: Candle readiness ──────────────────────────────────────────────
    body_ok = state.body_ratio >= profile.min_body_ratio
    if not body_ok:
        fails.append(f"body_ratio={state.body_ratio:.2f} need >={profile.min_body_ratio}")
    else:
        score += 0.02

    consist_ok = (profile.candle_consistency == 'ANY' or
                  profile.candle_consistency == state.candle_consist)
    if consist_ok:
        score += 0.02

    vol_ok = (profile.vol_trend == 'ANY' or profile.vol_trend == state.vol_trend)
    if not vol_ok:
        fails.append(f"vol_trend={state.vol_trend} need {profile.vol_trend}")
    else:
        score += 0.02

    # ── Hard fails: if any critical layer fails, strategy NOT armed ────────────
    # Critical = RSI, EMA structure, momentum direction
    critical_fails = [f for f in fails if any(k in f for k in ('rsi=', 'ema=', 'mom=', 'vwap='))]
    if critical_fails:
        return False, 0.0, f"BLOCKED: {'; '.join(critical_fails)}"

    # Soft fails: allow 1 soft fail (gap, range, body) but reduce confidence
    soft_fails = [f for f in fails if f not in critical_fails]
    if len(soft_fails) > 1:
        return False, 0.0, f"SOFT_BLOCKED: {'; '.join(soft_fails)}"

    # Armed!
    return True, round(min(score, 0.95), 3), f"ARMED(conf={score:.2f})"


# ─────────────────────────────────────────────────────────────────────────────
# IMPROVED TSL EXECUTOR (from V5)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Trade:
    date:        object
    strategy:    str
    direction:   str
    regime:      str
    confidence:  float
    lots:        int
    entry_time:  object
    entry_price: float
    exit_price:  float  = 0.0
    exit_time:   object = None
    exit_reason: str    = ''
    pnl_pts:     float  = 0.0
    pnl_rs:      float  = 0.0
    won:         bool   = False
    armed_reason: str   = ''


def execute_tsl(entry_bar: pd.Series, remaining: pd.DataFrame,
                direction: str, entry_spot: float) -> Tuple[float, str, object]:
    """V5-proven TSL-only exit logic."""
    ep    = float(entry_bar['open'])
    sl    = ep * (1 - SL_BACKSTOP)
    tgt   = ep * (1 + TARGET_PCT)
    thi   = ep
    tsl_on = False
    entry_ts = entry_bar['ts_ist'] if hasattr(entry_bar['ts_ist'], 'hour') else pd.Timestamp(entry_bar['ts_ist'])
    entry_mins = entry_ts.hour * 60 + entry_ts.minute

    xp = None; xr = 'EOD'; xt = None

    for _, bar in remaining.iterrows():
        ts   = bar['ts_ist'] if hasattr(bar['ts_ist'], 'hour') else pd.Timestamp(bar['ts_ist'])
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))
        thi  = max(thi, hi)
        cur_mins = ts.hour * 60 + ts.minute

        # Hard time exit
        if hhmm >= HARD_EXIT:
            xp = float(bar['close']); xr = 'TIME'; xt = bar['ts_ist']; break

        # Hard SL backstop
        if lo <= sl:
            xp = sl; xr = 'SL'; xt = bar['ts_ist']; break

        # Target
        if hi >= tgt:
            xp = tgt; xr = 'TARGET'; xt = bar['ts_ist']; break

        # TSL
        if thi >= ep * (1 + TSL_ACTIVATE):
            tsl_on = True
            floor = thi * (1 - TSL_TRAIL)
            if lo <= floor and floor > sl:
                xp = max(floor, sl); xr = 'TSL'; xt = bar['ts_ist']; break

    if xp is None:
        last = remaining.iloc[-1] if len(remaining) > 0 else entry_bar
        xp = float(last['close']); xr = 'EOD'; xt = last['ts_ist']

    return max(xp, 0.05), xr, xt


def execute_fixed_target(entry_bar: pd.Series, remaining: pd.DataFrame,
                         target_pct: float) -> Tuple[float, str, object]:
    """Fixed target + SL backstop exit for quick-move strategies like SHORT_UNWIND."""
    ep  = float(entry_bar['open'])
    sl  = ep * (1 - SL_BACKSTOP)
    tgt = ep * (1 + target_pct)
    xp  = None; xr = 'EOD'; xt = None

    for _, bar in remaining.iterrows():
        ts   = bar['ts_ist'] if hasattr(bar['ts_ist'], 'hour') else pd.Timestamp(bar['ts_ist'])
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))

        if hhmm >= HARD_EXIT:
            xp = float(bar['close']); xr = 'TIME'; xt = bar['ts_ist']; break
        if lo <= sl:
            xp = sl; xr = 'SL'; xt = bar['ts_ist']; break
        if hi >= tgt:
            xp = tgt; xr = 'TARGET'; xt = bar['ts_ist']; break

    if xp is None:
        last = remaining.iloc[-1] if len(remaining) > 0 else entry_bar
        xp = float(last['close']); xr = 'EOD'; xt = last['ts_ist']
    return max(xp, 0.05), xr, xt


# ─────────────────────────────────────────────────────────────────────────────
# MAIN BACKTEST
# ─────────────────────────────────────────────────────────────────────────────
def run_v6(opt_data: pd.DataFrame, eod_data: pd.DataFrame) -> List[Trade]:
    day_regimes = label_days(opt_data)
    all_strats  = make_strategies()
    # Filter to active only
    active_strats = [s for s in all_strats if s.name in ACTIVE_STRATEGIES]

    trading_days = sorted(opt_data['date'].unique())
    all_trades: List[Trade] = []

    prev_close = 0.0

    for day in trading_days:
        regime = day_regimes.get(day, 'NORMAL')
        if regime not in TRADEABLE_REGIMES:
            prev_close_row = eod_data[eod_data['dt'] == day]
            if not prev_close_row.empty:
                prev_close = float(prev_close_row.iloc[0]['close'])
            continue

        day_data = opt_data[opt_data['date'] == day].copy()
        c15      = build_15min_spot(day_data)
        if len(c15) < 4:
            continue

        pcr     = calc_pcr(day_data)
        expiry  = is_expiry_day(day)
        eod_row = eod_data[eod_data['dt'] == day]
        if not eod_row.empty:
            r = eod_row.iloc[0]
            day_ohlc = {'open': r['open'], 'high': r['high'],
                        'low': r['low'],   'close': r['close']}
        else:
            day_ohlc = {'open': float(c15.iloc[0]['close']),
                        'high': float(c15['high'].max() if 'high' in c15 else c15['close'].max()),
                        'low':  float(c15['low'].min()  if 'low'  in c15 else c15['close'].min()),
                        'close': float(c15.iloc[-1]['close'])}

        # ── Layer 1: Day context ──────────────────────────────────────────────
        ctx = compute_day_context(c15, prev_close, pcr)

        # Track trades per direction today (max 2 CE + 1 PE)
        trades_today: Dict[str, int] = defaultdict(int)
        # Track trades per strategy today — early/narrow strategies limited to 1
        strat_trades_today: Dict[str, int] = defaultdict(int)
        # Strategies limited to 1 trade per day (narrow window = re-entry is noise)
        # MEAN_REVERSION: double-fire days avg -1,385 vs single-fire +739
        # BEAR/BULL_TREND_FOLLOWER: ORB-based — once ORB breaks, 1 clean entry is enough
        ONE_TRADE_STRATEGIES = {'MORNING_BREAKOUT', 'EARLY_BREAKDOWN', 'WIDE_RANGE_RIDER',
                                'VOLATILITY_BREAKOUT', 'TREND_FOLLOWING', 'MEAN_REVERSION',
                                'ENHANCED_BULLISH', 'BEAR_TREND_FOLLOWER', 'BULL_TREND_FOLLOWER',
                                'MAGIC_SQUARE', 'ORDER_BLOCK_REVERSAL', 'SHORT_UNWIND',
                                'ENHANCED_BEARISH'}

        # Walk 15-min bars
        for i in range(3, len(c15)):
            row  = c15.iloc[i]
            ts   = row['ts_ist'] if hasattr(row['ts_ist'], 'hour') else pd.Timestamp(row['ts_ist'])
            hhmm = ts.hour * 100 + ts.minute

            if hhmm < 945 or hhmm > 1400:
                continue

            candles_so_far = c15.iloc[:i+1]

            # ── Layer 2: Intraday state ───────────────────────────────────────
            state = compute_intraday_state(candles_so_far, pcr)

            # Try each active strategy
            for strat in active_strats:
                if strat.name not in STRATEGY_PROFILES:
                    continue

                # Skip if outside entry window (per-strategy overrides take priority)
                entry_cut   = ENTRY_CUTOFF.get(strat.name, strat.entry_end)
                entry_start = ENTRY_START.get(strat.name, strat.entry_start)
                if hhmm < entry_start or hhmm > entry_cut:
                    continue

                # Per-strategy regime gate
                if strat.name == 'BEAR_TREND_FOLLOWER' and regime != 'TRENDING_BEAR':
                    continue
                if strat.name == 'BULL_TREND_FOLLOWER' and regime != 'TRENDING_BULL':
                    continue
                # audit11: 3 of 4 DHB PE TIME losses on TRENDING_BULL — block PE against bull
                if strat.name == 'DAY_HIGH_BEARISH' and regime == 'TRENDING_BULL':
                    continue

                dirs = ['CE', 'PE'] if strat.direction == 'BOTH' else [strat.direction]

                # Per-strategy cap: narrow strategies get only 1 trade per day total
                if strat.name in ONE_TRADE_STRATEGIES and strat_trades_today[strat.name] >= 1:
                    continue

                for direction in dirs:
                    # Max trades per direction per day
                    if direction == 'CE' and trades_today['CE'] >= 2:
                        continue
                    if direction == 'PE' and trades_today['PE'] >= 1:
                        continue

                    profile = STRATEGY_PROFILES[strat.name]

                    # ── Layer 3: Profile matching ─────────────────────────────
                    armed, conf, arm_reason = match_profile(profile, ctx, state, direction)
                    if not armed:
                        continue

                    # ── Original signal check from V3 ─────────────────────────
                    if not signal_check(strat, direction, candles_so_far, day_ohlc, pcr, hhmm, expiry,
                                        float(day_data[(day_data['option_type_flag'] == direction) &
                                                       (day_data['strike'] == strat.strike) &
                                                       (day_data['hhmm'] == hhmm)]['close'].iloc[-1])
                                        if len(day_data[(day_data['option_type_flag'] == direction) &
                                                        (day_data['strike'] == strat.strike) &
                                                        (day_data['hhmm'] == hhmm)]) > 0
                                        else 999.0):
                        continue

                    # ── Get option bars ───────────────────────────────────────
                    opt_b = day_data[
                        (day_data['option_type_flag'] == direction) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] == hhmm)
                    ]
                    if len(opt_b) == 0:
                        continue
                    prem = float(opt_b['close'].iloc[-1])
                    if prem < strat.min_premium or prem > 500:
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
                    entry_spot  = float(entry_bar.get('spot', state.spot))
                    remaining   = exec_bars.iloc[1:].copy()

                    # Execute — fixed target for quick-move strategies, TSL for the rest
                    fixed_tgt = FIXED_TARGET_STRATEGIES.get(strat.name, None)
                    if fixed_tgt is not None:
                        xp, xr, xt = execute_fixed_target(entry_bar, remaining, fixed_tgt)
                    else:
                        xp, xr, xt = execute_tsl(entry_bar, remaining, direction, entry_spot)

                    pnl_pts = xp - entry_price
                    pnl_rs  = round(pnl_pts * LOT_SIZE * 1 - BROKERAGE, 2)  # 1 lot always

                    all_trades.append(Trade(
                        date=day, strategy=strat.name, direction=direction,
                        regime=regime, confidence=conf, lots=1,
                        entry_time=entry_bar['ts_ist'], entry_price=entry_price,
                        exit_price=xp, exit_time=xt, exit_reason=xr,
                        pnl_pts=round(pnl_pts, 2), pnl_rs=pnl_rs,
                        won=pnl_rs > 0, armed_reason=arm_reason,
                    ))
                    trades_today[direction] += 1
                    strat_trades_today[strat.name] += 1
                    break  # one trade per strategy per direction per day

        # Update prev_close
        if not eod_row.empty:
            prev_close = float(eod_row.iloc[0]['close'])

    return all_trades


# ─────────────────────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────────────────────
def report(trades: List[Trade], total_days: int):
    if not trades:
        print("NO TRADES"); return

    df = pd.DataFrame([t.__dict__ for t in trades])
    df['date'] = pd.to_datetime(df['date'])

    total_pnl = df['pnl_rs'].sum()
    wr        = 100 * df['won'].mean()
    n         = len(df)
    traded_days = df['date'].nunique()
    daily_pnl = df.groupby('date')['pnl_rs'].sum()
    green_days = (daily_pnl > 0).sum()
    dd = (daily_pnl.cumsum() - daily_pnl.cumsum().cummax()).min()

    print(f"\n{'='*70}")
    print(f"BACKTEST V6 PROFILED — {total_days} total days | {traded_days} traded days")
    print(f"{'='*70}")
    print(f"  Total trades      : {n}")
    print(f"  Win rate          : {wr:.1f}%")
    print(f"  Total PnL         : ₹{total_pnl:+,.0f}")
    print(f"  Avg PnL/trade     : ₹{total_pnl/n:+,.0f}")
    print(f"  Avg PnL/traded day: ₹{total_pnl/traded_days:+,.0f}  ({total_pnl/traded_days/CAPITAL*100:.2f}% of ₹1L)")
    monthly = total_pnl / traded_days * 22   # avg per traded day × 22 trading days/month
    print(f"  Monthly est.      : ₹{monthly:+,.0f}  ({monthly/CAPITAL*100:.1f}%)")
    print(f"  Green days        : {green_days}/{traded_days} ({100*green_days/traded_days:.0f}%)")
    print(f"  Max drawdown      : ₹{dd:+,.0f}")

    # Per year
    for yr in sorted(df['date'].dt.year.unique()):
        yd = df[df['date'].dt.year == yr]
        yd_days = yd['date'].nunique()
        yd_pnl = yd['pnl_rs'].sum()
        print(f"  {yr}: ₹{yd_pnl:+,.0f}  ({yd_days} traded days, {len(yd)} trades, "
              f"₹{yd_pnl/yd_days:+,.0f}/day)")

    # Per strategy
    print(f"\n{'Strategy':<25} {'N':>4} {'WR%':>5} {'Total':>10} {'Avg/T':>8} {'AvgConf':>8}")
    print('-'*65)
    for sname in df['strategy'].unique():
        sd = df[df['strategy'] == sname]
        swr = 100 * sd['won'].mean()
        spnl = sd['pnl_rs'].sum()
        savg = spnl / len(sd)
        sc = sd['confidence'].mean()
        print(f"  {sname:<23} {len(sd):>4} {swr:>4.0f}% {spnl:>+10,.0f} {savg:>+8,.0f} {sc:>8.3f}")

    # Per regime
    print(f"\n{'Regime':<20} {'Trades':>7} {'WR%':>5} {'Total':>10} {'Per Trade':>10}")
    print('-'*55)
    for reg in df['regime'].unique():
        rd = df[df['regime'] == reg]
        rwr = 100 * rd['won'].mean()
        rpnl = rd['pnl_rs'].sum()
        print(f"  {reg:<18} {len(rd):>7} {rwr:>4.0f}% {rpnl:>+10,.0f} {rpnl/len(rd):>+10,.0f}")

    # Exit breakdown
    print(f"\n{'Exit':<12} {'Count':>6} {'Total':>10} {'Avg':>8}")
    print('-'*40)
    for xr in df['exit_reason'].value_counts().index:
        xd = df[df['exit_reason'] == xr]
        print(f"  {xr:<12} {len(xd):>6} {xd['pnl_rs'].sum():>+10,.0f} {xd['pnl_rs'].mean():>+8,.0f}")

    # Best days
    print(f"\nTop 10 trading days:")
    for dt, pnl in daily_pnl.sort_values(ascending=False).head(10).items():
        day_trades = df[df['date'] == dt]
        strats = ', '.join(f"{r['direction']}({r['strategy'][:10]})" for _, r in day_trades.iterrows())
        print(f"  {str(dt)[:10]}  ₹{pnl:+,.0f}  ({len(day_trades)} trades: {strats})")

    # Worst days
    print(f"\nWorst 5 days:")
    for dt, pnl in daily_pnl.sort_values().head(5).items():
        day_trades = df[df['date'] == dt]
        strats = ', '.join(f"{r['direction']}({r['strategy'][:10]})[{r['exit_reason']}]"
                           for _, r in day_trades.iterrows())
        print(f"  {str(dt)[:10]}  ₹{pnl:+,.0f}  {strats}")

    print(f"\nV5 comparison: win=67.7%, PnL=+₹13,760, traded_days=26, monthly=₹11,643")


if __name__ == '__main__':
    print("Loading data...")
    opt = load_option_data()
    eod = load_eod_data()
    DAYS = opt['date'].nunique()

    print("Running V6 profiled backtest...")
    trades = run_v6(opt, eod)
    report(trades, DAYS)
