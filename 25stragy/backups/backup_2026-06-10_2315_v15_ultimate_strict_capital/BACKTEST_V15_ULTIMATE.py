#!/usr/bin/env python3
"""
BACKTEST V8 AI — Scaling Multi-Strategy Trading Engine
=====================================================
Optimized version of the multi-index execution engine.

Key Improvements:
1. Full Strategy Matrix Activation: Integrates and defines all 36 strategies (26 base + 10 Tier 5).
2. Non-NIFTY Breakout Bug Fix: Eliminates the shortcut that bypassed breakout triggers on
   BANKNIFTY, FINNIFTY, and SENSEX. Uses an index-aware `signal_check` that applies percentage-based
   conditions and index-specific wide range points (cfg.wide_range_pts).
3. Dynamic Multi-Lot Scaling: Position sizes are dynamically scaled based on Strategy Tier
   and intraday profile confidence (conf).
4. Daily PnL Circuit Breaker: Prevents runaway drawdown on bad days by blocking new entries
   if index PnL for the day falls below -10% of capital (Rs. -10,000).
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

# Import V6 configurations
from BACKTEST_V6_PROFILED import (
    FIXED_TARGET_STRATEGIES,
    TRADEABLE_REGIMES, STRATEGY_PROFILES,
    StrategyProfile, compute_day_context, compute_intraday_state,
    match_profile,
)
from BACKTEST_V3_TUNED import (
    PERIODS, STRIKES, OPT_TYPES, calc_pcr, build_15min_spot,
)
from regime_detector import label_days

TRADEABLE_REGIMES = {'NORMAL', 'TRENDING_BEAR', 'TRENDING_BULL', 'RANGE_BOUND'}

# V10.0 Optimization Flags
ENABLE_REGIME_SCALING = os.environ.get("ENABLE_REGIME_SCALING", "FALSE").upper() == "TRUE"
ENABLE_EXPIRY_UNCAP = os.environ.get("ENABLE_EXPIRY_UNCAP", "TRUE").upper() == "TRUE"
EXPIRY_UNCAP_TIGHT = os.environ.get("EXPIRY_UNCAP_TIGHT", "TRUE").upper() == "TRUE"
ENABLE_THRESH_RELAX = os.environ.get("ENABLE_THRESH_RELAX", "FALSE").upper() == "TRUE"

UTC_OFFSET = pd.Timedelta(hours=5, minutes=30)
RAW_DIR    = 'c:/cursor/options/niftyopt/data/raw'
CAPITAL_BASE = 500_000
CAPITAL = CAPITAL_BASE 

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE CONFIGURATION LOADER (JSON)
# ─────────────────────────────────────────────────────────────────────────────
import json
import os

CONFIG_PATH = r"C:\25stragy\config_ultimate.json"
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = "config_ultimate.json"

STRATEGY_DNA_PATH = r"C:\25stragy\strategy_dna.json"
if not os.path.exists(STRATEGY_DNA_PATH):
    STRATEGY_DNA_PATH = "strategy_dna.json"

with open(CONFIG_PATH, "r") as f:
    config_db = json.load(f)

with open(STRATEGY_DNA_PATH, "r") as f:
    strategy_db = json.load(f)

# Global variables loaded from config.json
CAPITAL_BASE = config_db["system"].get("capital_base", 500000)
CAPITAL = CAPITAL_BASE
MAX_TEST_LOTS = config_db["system"].get("max_test_lots", 3)
GLOBAL_BROKERAGE = config_db["system"].get("global_brokerage", 40.0)
DAILY_CIRCUIT_BREAKER_RS = config_db["system"].get("daily_circuit_breaker_rs", -10000)

CAPITAL_PER_INDEX = config_db["system"].get("capital_per_index", 125000)
TIER1_DEPLOY_PCT = config_db["system"].get("tier1_deploy_pct", 0.60)
TIER2_DEPLOY_PCT = config_db["system"].get("tier2_deploy_pct", 0.50)
TIER3_DEPLOY_PCT = config_db["system"].get("tier3_deploy_pct", 0.40)
TIER4_DEPLOY_PCT = config_db["system"].get("tier4_deploy_pct", 0.30)
MAX_LOTS_CAP = config_db["system"].get("max_lots_cap", 20)
SPOT_SL_PCT = config_db["system"].get("spot_sl_pct", 0.0035)

def get_tier_deploy_pct(strat_name: str) -> float:
    tier1 = {'BULL_TREND_FOLLOWER', 'BEAR_TREND_FOLLOWER', 'DAY_LOW_BULLISH', 'DAY_HIGH_BEARISH'}
    tier2 = {'MAGIC_SQUARE', 'WIDE_RANGE_RIDER', 'MEAN_REVERSION', 'ORDER_BLOCK_REVERSAL', 'VOLATILITY_BREAKOUT', 'EARLY_BREAKDOWN', 'MORNING_BREAKOUT'}
    tier3 = {'ENHANCED_BEARISH', 'ENHANCED_BULLISH', 'ULTIMATE_DAY_HIGH_LOW', 'SCALPING', 'OPTIONS_GREEKS', 'AI_ENHANCED', 'BREAKOUT', 'GAMMA_BLAST', 'ZERO_HERO', 'LONG_UNWIND', 'PUT_WRITER_SUPPORT', 'RESIST_BREAK', 'DAY_HIGH_LOW_TRADITIONAL'}
    if strat_name in tier1:
        return TIER1_DEPLOY_PCT
    elif strat_name in tier2:
        return TIER2_DEPLOY_PCT
    elif strat_name in tier3:
        return TIER3_DEPLOY_PCT
    else:
        return TIER4_DEPLOY_PCT

@dataclass
class IndexConfig:
    name:          str
    lot_size:      int
    atm_step:      float
    expiry_dow:    int
    brokerage:     float = 40.0
    premium_scale: float = 1.0
    hard_exit:     int   = 1415
    max_ce_day:    int   = 1
    wide_range_pts: float = 150.0
    entry_cutoff:   int   = 1400
    slippage_pts:   float = 0.5

INDEX_CONFIGS: Dict[str, IndexConfig] = {}
INDEX_TSL_MULTIPLIERS = {}
for idx_name, idx_cfg in config_db["index_profiles"].items():
    INDEX_CONFIGS[idx_name] = IndexConfig(
        name=idx_name,
        lot_size=idx_cfg["lot_size"],
        atm_step=idx_cfg["atm_step"],
        expiry_dow=idx_cfg["expiry_dow"],
        brokerage=idx_cfg.get("brokerage", GLOBAL_BROKERAGE),
        premium_scale=idx_cfg.get("premium_scale", 1.0),
        hard_exit=idx_cfg.get("hard_exit", 1430),
        max_ce_day=idx_cfg.get("max_ce_day", 2),
        wide_range_pts=idx_cfg.get("wide_range_pts", 120.0),
        entry_cutoff=idx_cfg.get("entry_cutoff", 1430),
        slippage_pts=idx_cfg.get("slippage_pts", 0.5)
    )
    INDEX_TSL_MULTIPLIERS[idx_name] = idx_cfg.get("tsl_multipliers", {"activate": 1.0, "trail": 0.6, "target": 1.0})

# Base Strategy DNA loaded from strategy_dna.json
BASE_STRATEGY_DNA = {}
for name, data in strategy_db["strategies"].items():
    BASE_STRATEGY_DNA[name] = {
        'tsl_a': data["tsl_a"],
        'tsl_t': data["tsl_t"],
        'tgt': data["tgt"],
        'sl': data["sl"],
        'thresh': data["thresh"],
        'max_d': data["max_d"],
        'min_p': data["min_p"],
        'max_p': data["max_p"],
        'boost': data["boost"]
    }

# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY DNA FRAMEWORK
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class IndexStrategyDNA:
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

def build_dna_matrix() -> Dict[str, IndexStrategyDNA]:
    matrix = {}
    for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']:
        multipliers = INDEX_TSL_MULTIPLIERS[idx]
        for strat_name, base in BASE_STRATEGY_DNA.items():
            tsl_a = min(0.20, base['tsl_a'] * multipliers['activate'])
            tsl_t = min(0.15, base['tsl_t'] * multipliers['trail'])
            tgt = min(2.50, base['tgt'] * multipliers['target'])
            
            key = f"{idx}:{strat_name}"
            matrix[key] = IndexStrategyDNA(
                index=idx,
                strategy=strat_name,
                tsl_activate=round(tsl_a, 4),
                tsl_trail=round(tsl_t, 4),
                target_pct=round(tgt, 4),
                sl_backstop=base['sl'],
                entry_threshold=base['thresh'],
                max_trades_per_day=base['max_d'],
                min_premium=base['min_p'],
                max_premium=base['max_p'],
                confidence_boost=base['boost'],
                notes=f"{idx} {strat_name}: A{round(tsl_a,2)}/T{round(tsl_t,2)}/G{round(tgt,2)}"
            )
    return matrix

INDEX_STRATEGY_DNA_MATRIX = build_dna_matrix()

def get_index_strategy_dna(index: str, strategy: str) -> IndexStrategyDNA:
    key = f"{index}:{strategy}"
    if key in INDEX_STRATEGY_DNA_MATRIX:
        return INDEX_STRATEGY_DNA_MATRIX[key]
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

class StrategyDNA:
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

# Active strategies configuration loaded dynamically from config.json
ACTIVE_STRATEGIES_BY_INDEX = {}
for idx_name, idx_cfg in config_db["index_profiles"].items():
    ACTIVE_STRATEGIES_BY_INDEX[idx_name] = set(idx_cfg.get("active_strategies", []))
ACTIVE_STRATEGIES = set(BASE_STRATEGY_DNA.keys())
print(f"[DNA MATRIX] Loaded {len(ACTIVE_STRATEGIES)} strategies x 4 indices = {len(INDEX_STRATEGY_DNA_MATRIX)} DNA combinations")

# ─────────────────────────────────────────────────────────────────────────────
# Strategy Definitions class local definition
# ─────────────────────────────────────────────────────────────────────────────
from BACKTEST_V3_TUNED import StrategyDef

def make_strategies_v8() -> List[StrategyDef]:
    strats = []
    for name, data in strategy_db["strategies"].items():
        s = StrategyDef(
            name=name,
            direction=data.get("direction", "BOTH"),
            strike=data.get("strike", "ATM"),
            entry_start=data.get("entry_start", 1000),
            entry_end=data.get("entry_end", 1430),
            sl_pct=data.get("sl", 0.15),
            target_pct=data.get("tgt", 0.25),
            tsl_pts=data.get("tsl_t", 0.10) * 100,
            min_premium=data.get("min_p", 30.0),
            max_premium=data.get("max_p", 400.0),
            require_vwap=data.get("require_vwap", False),
            require_volume=data.get("require_volume", False),
            direction_bias=data.get("direction_bias", "")
        )
        strats.append(s)
    return strats

# ─────────────────────────────────────────────────────────────────────────────
# INDICATOR FUNCTIONS (Local implementation for self-containment)
# ─────────────────────────────────────────────────────────────────────────────
def calc_rsi(closes: pd.Series, n: int = 14) -> float:
    if len(closes) < n:
        return 50.0
    delta = pd.Series(closes).diff()
    gain  = delta.clip(lower=0).ewm(com=n-1, min_periods=n).mean()
    loss  = (-delta).clip(lower=0).ewm(com=n-1, min_periods=n).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = (100 - 100 / (1 + rs)).fillna(50)
    return float(rsi.iloc[-1])

def calc_vwap(candles15: pd.DataFrame) -> float:
    typ = (candles15['high'] + candles15['low'] + candles15['close']) / 3
    vol = candles15['volume'].replace(0, 1)
    return float((typ * vol).sum() / vol.sum())

# ─────────────────────────────────────────────────────────────────────────────
# INDEX-AWARE SIGNAL CHECK (Fixes non-NIFTY breakout bug)
# ─────────────────────────────────────────────────────────────────────────────
def signal_check(strat: StrategyDef, direction: str,
                 candles15: pd.DataFrame,
                 day_ohlc: dict, pcr: float,
                 current_hhmm: int, is_expiry: bool,
                 opt_premium: float, cfg: IndexConfig) -> bool:

    if len(candles15) < (2 if strat.name == 'OPENING_DRIVE' else 3):
        return False

    # Premium filter
    if opt_premium < (strat.min_premium * cfg.premium_scale) or opt_premium > (strat.max_premium * cfg.premium_scale):
        return False

    c    = candles15.iloc[-1]
    p    = candles15.iloc[-2]
    spot = float(c['close'])
    closes = candles15['close'].values.astype(float)
    highs  = candles15['high'].values.astype(float)
    lows   = candles15['low'].values.astype(float)
    vols   = candles15['volume'].values.astype(float)

    rsi   = calc_rsi(pd.Series(closes))
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

    above_vwap = spot > vwap
    below_vwap = spot < vwap

    if strat.require_vwap:
        if direction == 'CE' and not above_vwap:
            return False
        if direction == 'PE' and not below_vwap:
            return False

    if strat.require_volume and not vol_spike:
        return False

    n = strat.name
    d = direction

    # ── BASE 26 STRATEGY TRIGGERS ──
    if n == 'ULTIMATE_DAY_HIGH_LOW':
        if len(candles15) < 2:
            return False
        prev_c = candles15.iloc[-2]
        prev_lo   = float(prev_c['low'])
        prev_hi   = float(prev_c['high'])
        prev_cl   = float(prev_c['close'])
        prev_op   = float(prev_c['open'])
        prev_green = prev_cl > prev_op
        prev_red   = prev_cl < prev_op
        run_high = float(candles15.iloc[:-1]['high'].max())
        run_low  = float(candles15.iloc[:-1]['low'].min())
        near_low  = prev_lo <= run_low * 1.0015
        near_high = prev_hi >= run_high * 0.9985
        bodies = [abs(float(candles15.iloc[k]['close']) - float(candles15.iloc[k]['open']))
                  for k in range(max(0, len(candles15)-6), len(candles15)-1)]
        avg_body = sum(bodies) / len(bodies) if bodies else 0
        prev_body = abs(prev_cl - prev_op)
        strong_candle = prev_body >= avg_body * 0.8
        if d == 'CE':
            return near_low and prev_green and strong_candle and rsi > 35
        if d == 'PE':
            return near_high and prev_red and strong_candle and rsi < 45

    elif n == 'DAY_HIGH_BEARISH':
        near_high = abs(spot - day_high) / day_high < 0.004
        rejection = float(c['close']) < float(p['low'])
        if d == 'PE': return (near_high or rejection) and rsi > 58

    elif n == 'DAY_LOW_BULLISH':
        near_low = abs(spot - day_low) / day_low < 0.004
        bounce   = float(c['close']) > float(p['high'])
        if d == 'CE': return (near_low or bounce) and (rsi < 47 or pcr > 1.2)

    elif n == 'DAY_HIGH_LOW_TRADITIONAL':
        if len(candles15) < 5:
            return False
        first_hour = candles15.iloc[:4]
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

    elif n == 'ENHANCED_BEARISH':
        if d == 'PE':
            return (rsi > 56 and ema5 < ema20 and c['close'] < c['open'])

    elif n == 'ENHANCED_BULLISH':
        if d == 'CE':
            ema_bullish = ema5 > ema20 * 0.999
            return (rsi < 46 and ema_bullish and c['close'] > c['open'])

    elif n == 'TREND_FOLLOWING':
        if d == 'PE': return (ema5 < ema20 and c['close'] < p['close'] and
                              rsi < 48 and below_vwap and candle_rng > avg5_rng * 0.8)

    elif n == 'AI_ENHANCED':
        bearish = (ema5 < ema20 and pcr < 1.0 and rsi > 52 and c['close'] < c['open'])
        bullish = (ema5 > ema20 and pcr > 1.3 and rsi < 55 and c['close'] > c['open'])
        if d == 'CE': return bullish
        if d == 'PE': return bearish

    elif n == 'MEAN_REVERSION':
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

    elif n == 'SCALPING':
        if d == 'CE':
            return (c['close'] > p['high'] and rsi > 50 and ema5 > ema20 and vol_spike)

    elif n == 'BREAKOUT':
        if len(candles15) >= 20 and d == 'PE':
            recent_low = float(pd.Series(lows[:-1]).tail(20).min())
            return (spot < recent_low * 0.999 and rsi < 45 and vol_spike)

    elif n == 'VOLATILITY_BREAKOUT':
        if d == 'PE':
            return (candle_rng >= avg5_rng * 1.3 and c['close'] < c['open'] and c['close'] < p['low'] and rsi < 48)
        if d == 'CE':
            return (candle_rng >= avg5_rng * 1.3 and c['close'] > c['open'] and c['close'] > p['high'] and rsi > 52)

    elif n == 'OPTIONS_GREEKS':
        if d == 'PE':
            return (rsi > 58 and c['close'] < c['open'] and candle_rng > avg5_rng)
        if d == 'CE':
            return (rsi < 42 and c['close'] > c['open'] and candle_rng > avg5_rng)

    elif n == 'SHORT_UNWIND':
        if d == 'CE':
            return (pcr < 1.0 and ema5 > ema20 and rsi > 52 and above_vwap)

    elif n == 'LONG_UNWIND':
        if d == 'PE':
            return (pcr > 1.3 and ema5 < ema20 and rsi < 48)

    elif n == 'PUT_WRITER_SUPPORT':
        if d == 'CE':
            return (pcr > 1.05 and rsi < 50 and c['close'] > c['open'] and abs(spot - day_low) / day_low < 0.020)

    elif n == 'RESIST_BREAK':
        if len(candles15) >= 5 and d == 'CE':
            resist = float(pd.Series(highs[:-1]).tail(5).max())
            return (spot > resist * 1.002 and rsi > 55 and ema5 > ema20 and vol_spike)

    elif n == 'MAGIC_SQUARE':
        day_range = day_high - day_low
        fib_618   = day_low + day_range * 0.618
        fib_382   = day_low + day_range * 0.382
        near_618  = abs(spot - fib_618) / (spot + 0.01) < 0.005
        near_382  = abs(spot - fib_382) / (spot + 0.01) < 0.005
        if d == 'PE': return (near_618 and rsi > 55 and ema5 < ema20)
        if d == 'CE': return (near_382 and rsi < 45 and ema5 > ema20)

    elif n == 'ORDER_BLOCK_REVERSAL':
        if len(candles15) >= 4:
            ranges = highs[-5:-1] - lows[-5:-1] if len(highs) >= 5 else highs[:-1] - lows[:-1]
            if len(ranges) == 0: return False
            idx         = int(np.argmax(ranges))
            strong_high = float(highs[max(0,len(highs)-5):-1][idx])
            strong_low  = float(lows[max(0,len(lows)-5):-1][idx])
            if d == 'PE':
                at_resist = abs(spot - strong_high) / strong_high < 0.007
                return (at_resist and rsi > 56 and c['close'] < c['open'] and ema5 < ema20)
            if d == 'CE':
                at_support = abs(spot - strong_low) / strong_low < 0.007
                return (at_support and rsi < 44 and c['close'] > c['open'] and ema5 > ema20)

    elif n == 'ZERO_HERO':
        if not is_expiry: return False
        if d == 'CE': return (c['close'] > c['open'] and ema5 > ema20 and rsi > 48)
        if d == 'PE': return (c['close'] < c['open'] and ema5 < ema20 and rsi < 52)

    elif n == 'GAMMA_BLAST':
        if not is_expiry: return False
        if d == 'CE': return (candle_rng >= avg5_rng * 1.3 and c['close'] > c['open'] and rsi > 48 and c['close'] > ema5)
        if d == 'PE': return (candle_rng >= avg5_rng * 1.3 and c['close'] < c['open'] and rsi < 52 and c['close'] < ema5)

    elif n == 'MORNING_BREAKOUT':
        if d == 'CE' and len(candles15) >= 4:
            first_hour = candles15.iloc[:4]
            orb_high = float(first_hour['high'].max())
            breakout = spot > orb_high * 1.001
            return (breakout and above_vwap and rsi > 53 and ema5 > ema20 and c['close'] > c['open'])

    elif n == 'EARLY_BREAKDOWN':
        if d == 'PE' and len(candles15) >= 4:
            first_hour = candles15.iloc[:4]
            orb_low = float(first_hour['low'].min())
            breakdown = spot < orb_low * 0.999
            return (breakdown and below_vwap and rsi < 47 and ema5 < ema20 and c['close'] < c['open'])

    elif n == 'WIDE_RANGE_RIDER':
        current_range = day_high - day_low
        if current_range < cfg.wide_range_pts:
            return False
        prev_rsi = calc_rsi(pd.Series(closes[:-1]))
        if d == 'CE':
            trend_up   = ema5 > ema20 and above_vwap
            pullback   = prev_rsi < 60 and rsi > 50
            green_bar  = c['close'] > c['open']
            return (trend_up and pullback and green_bar and current_range > cfg.wide_range_pts)
        if d == 'PE':
            trend_down = ema5 < ema20 and below_vwap
            pullback   = prev_rsi > 40 and rsi < 50
            red_bar    = c['close'] < c['open']
            return (trend_down and pullback and red_bar and current_range > cfg.wide_range_pts)

    elif n == 'BEAR_TREND_FOLLOWER':
        if d == 'PE' and len(candles15) >= 4:
            first_hour = candles15.iloc[:4]
            orb_low    = float(first_hour['low'].min())
            breakdown  = spot < orb_low * 0.999
            return (breakdown and below_vwap and rsi < 50 and ema5 < ema20 and c['close'] < c['open'])

    elif n == 'BULL_TREND_FOLLOWER':
        if d == 'CE' and len(candles15) >= 4:
            first_hour = candles15.iloc[:4]
            orb_high   = float(first_hour['high'].max())
            breakout   = spot > orb_high * 1.001
            return (breakout and above_vwap and rsi > 50 and ema5 > ema20 and c['close'] > c['open'])

    # ── TIER 5 NEW STRATEGY TRIGGERS ──
    elif n == 'MOMENTUM_BURST':
        if d == 'CE': return c['close'] > p['close'] and rsi > 60 and ema5 > ema20 and vol_spike
        if d == 'PE': return c['close'] < p['close'] and rsi < 40 and ema5 < ema20 and vol_spike

    elif n == 'VWAP_BOUNCE':
        # Rebound close to VWAP
        near_vwap = abs(spot - vwap) / vwap < 0.002
        if d == 'CE': return near_vwap and c['close'] > c['open'] and rsi > 50 and ema5 > ema20
        if d == 'PE': return near_vwap and c['close'] < c['open'] and rsi < 50 and ema5 < ema20

    elif n == 'OPENING_DRIVE':
        if len(candles15) < 3: return False
        # Entry on break of first bar in opening 30 mins
        orb_high_1st = float(candles15.iloc[0]['high'])
        orb_low_1st = float(candles15.iloc[0]['low'])
        if d == 'CE': return spot > orb_high_1st * 1.001 and rsi > 55 and c['close'] > c['open']
        if d == 'PE': return spot < orb_low_1st * 0.999 and rsi < 45 and c['close'] < c['open']

    elif n == 'PREMIUM_CRUSH':
        # Volatility contraction / Mean reversion
        n_bars = min(15, len(closes))
        if n_bars >= 5:
            bb_mid = float(pd.Series(closes).rolling(n_bars).mean().iloc[-1])
            bb_std = float(pd.Series(closes).rolling(n_bars).std().iloc[-1])
            if bb_std == 0: return False
            bb_up = bb_mid + 2.0 * bb_std
            bb_dn = bb_mid - 2.0 * bb_std
            if d == 'CE': return spot < bb_dn and rsi < 35 and c['close'] > c['open']
            if d == 'PE': return spot > bb_up and rsi > 65 and c['close'] < c['open']

    elif n == 'RSI_REVERSAL':
        # Extremes
        if d == 'CE': return rsi < 25 and c['close'] > c['open']
        if d == 'PE': return rsi > 75 and c['close'] < c['open']

    elif n == 'EMA_CROSSOVER':
        if len(closes) < 3: return False
        prev_closes = pd.Series(closes[:-1])
        prev_ema5 = float(prev_closes.ewm(span=5, adjust=False).mean().iloc[-1])
        prev_ema20 = float(prev_closes.ewm(span=20, adjust=False).mean().iloc[-1])
        if d == 'CE': return prev_ema5 <= prev_ema20 and ema5 > ema20 and rsi > 50
        if d == 'PE': return prev_ema5 >= prev_ema20 and ema5 < ema20 and rsi < 50

    elif n == 'BOLLINGER_SQUEEZE':
        n_bars = min(20, len(closes))
        if n_bars >= 5:
            bb_mid = float(pd.Series(closes).rolling(n_bars).mean().iloc[-1])
            bb_std = float(pd.Series(closes).rolling(n_bars).std().iloc[-1])
            bb_width = (2.0 * bb_std) / bb_mid if bb_mid > 0 else 1.0
            is_squeeze = bb_width < 0.005  # narrow bands
            bb_up = bb_mid + 2.0 * bb_std
            bb_dn = bb_mid - 2.0 * bb_std
            if d == 'CE': return is_squeeze and spot > bb_up and rsi > 55
            if d == 'PE': return is_squeeze and spot < bb_dn and rsi < 45

    elif n == 'VOLUME_CLIMAX':
        # Climax volume + rejection shadow
        is_vol_climax = cur_vol > avg5_vol * 3.0
        shadow_ratio = 1.0
        if candle_rng > 0:
            if d == 'CE':
                shadow_ratio = (min(c['open'], c['close']) - c['low']) / candle_rng
                return is_vol_climax and shadow_ratio > 0.6 and rsi < 40
            if d == 'PE':
                shadow_ratio = (c['high'] - max(c['open'], c['close'])) / candle_rng
                return is_vol_climax and shadow_ratio > 0.6 and rsi > 60

    elif n == 'ATR_BREAK':
        if len(highs) >= 4:
            prev_hi_3 = max(highs[-4:-1])
            prev_lo_3 = min(lows[-4:-1])
            if d == 'CE': return spot > prev_hi_3 + 0.1 * avg5_rng and rsi > 55 and c['close'] > c['open']
            if d == 'PE': return spot < prev_lo_3 - 0.1 * avg5_rng and rsi < 45 and c['close'] < c['open']

    elif n == 'MACD_DIVERGENCE':
        # RSI vs Price Divergence
        if len(closes) >= 5:
            prev_rsi_2 = calc_rsi(pd.Series(closes[:-2]))
            if d == 'CE': return lows[-1] < lows[-3] and rsi > prev_rsi_2 and c['close'] > c['open']
            if d == 'PE': return highs[-1] > highs[-3] and rsi < prev_rsi_2 and c['close'] < c['open']

    return False

# ─────────────────────────────────────────────────────────────────────────────
# PER-INDEX STRATEGY PROFILES
# ─────────────────────────────────────────────────────────────────────────────
def _make_profiles_for_index(idx: str) -> Dict[str, StrategyProfile]:
    if idx == 'NIFTY':
        profiles = STRATEGY_PROFILES.copy()
        for name in BASE_STRATEGY_DNA.keys():
            if name not in profiles:
                direction = 'CE' if 'BULL' in name or 'SUPPORT' in name or 'UNWIND' in name or 'CE' in name else ('PE' if 'BEAR' in name or 'DOWN' in name or 'PE' in name else 'BOTH')
                profiles[name] = StrategyProfile(
                    name=name, direction=direction,
                    gap_pct_range=(-1.5, 1.5), pcr_open_range=(0.0, 3.0),
                    rsi_range=(0, 100), ema_structure='ANY', vwap_side='ANY', momentum_dir='ANY',
                    range_consumed_min=0.0, range_consumed_max=1.0,
                    min_body_ratio=0.10, candle_consistency='ANY', vol_trend='ANY',
                    base_confidence=0.60
                )
        return profiles

    gap = {'BANKNIFTY': 3.0, 'FINNIFTY': 3.0, 'SENSEX': 3.0}[idx]
    pcr_up = {'BANKNIFTY': 6.0, 'FINNIFTY': 20.0, 'SENSEX': 40.0}[idx]
    rsi_adj = {'BANKNIFTY': 3, 'FINNIFTY': 2, 'SENSEX': 3}[idx]
    rc_adj = {'BANKNIFTY': 0.0, 'FINNIFTY': 0.0, 'SENSEX': 0.0}[idx]

    def pcr(lo=0.0, hi=3.0): return (lo, min(hi, pcr_up))
    def gap_r(lo, hi): return (-gap, gap)
    def rsi(lo, hi): return (max(0, lo - rsi_adj), min(100, hi + rsi_adj))
    def rc(lo, hi): return (max(0.0, lo + rc_adj), min(1.0, hi))

    profiles = {
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
            rsi_range=(30, 70),
            ema_structure='ANY', vwap_side='ANY', momentum_dir='ANY',
            range_consumed_min=0.50,
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
            gap_pct_range=(-gap*0.30, gap*0.30),
            pcr_open_range=pcr(0.0, 3.0),
            rsi_range=rsi(15, 44),
            ema_structure='BEAR', vwap_side='BELOW', momentum_dir='DOWN',
            range_consumed_min=0.10, range_consumed_max=0.60,
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

    # Add default profiles for any remaining active strategies
    for name in BASE_STRATEGY_DNA.keys():
        if name not in profiles:
            direction = 'CE' if 'BULL' in name or 'SUPPORT' in name or 'UNWIND' in name or 'CE' in name else ('PE' if 'BEAR' in name or 'DOWN' in name or 'PE' in name else 'BOTH')
            profiles[name] = StrategyProfile(
                name=name, direction=direction,
                gap_pct_range=gap_r(-gap, gap),
                pcr_open_range=pcr(0.0, pcr_up),
                rsi_range=(0, 100),
                ema_structure='ANY', vwap_side='ANY', momentum_dir='ANY',
                range_consumed_min=0.0, range_consumed_max=1.0,
                min_body_ratio=0.10, candle_consistency='ANY', vol_trend='ANY',
                base_confidence=0.60
            )
    return profiles

INDEX_PROFILES: Dict[str, Dict[str, StrategyProfile]] = {
    idx: _make_profiles_for_index(idx)
    for idx in INDEX_CONFIGS
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADER
# ─────────────────────────────────────────────────────────────────────────────
def load_option_data_for_index(idx_name: str) -> pd.DataFrame:
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
# TSL EXECUTOR (Index-Aware)
# ─────────────────────────────────────────────────────────────────────────────
def _get_ts(bar) -> pd.Timestamp:
    v = bar.get('ts_ist') if hasattr(bar, 'get') else getattr(bar, 'ts_ist', None)
    return pd.Timestamp(v) if v is not None else pd.Timestamp('2000-01-01')

def get_dynamic_hard_exit(index: str, strategy: str, regime: str, is_expiry: bool) -> int:
    is_reversal = any(x in strategy for x in ['REVERSAL', 'MEAN', 'BLOCK', 'CRUSH', 'CLIMAX', 'LOW_BULLISH', 'HIGH_BEARISH'])
    if is_expiry:
        return 1245 if is_reversal else 1330
    if regime in ['TRENDING_BULL', 'TRENDING_BEAR', 'EXPLOSIVE_GAP']:
        return 1330 if is_reversal else 1430
    return 1300 if is_reversal else 1430

def execute_fixed_target_idx(entry_bar: pd.Series, remaining: pd.DataFrame,
                             target_pct: float, hard_exit: int = 1415,
                             index_name: str = 'NIFTY', strat_name: str = '',
                             regime: str = 'NORMAL') -> Tuple[float, str, object]:
    dna = get_index_strategy_dna(index_name, strat_name)
    ep  = float(entry_bar['open'])
    sl_backstop = dna.sl_backstop
    if index_name == 'SENSEX':
        sl_backstop = min(sl_backstop, 0.20)
    elif index_name == 'BANKNIFTY':
        sl_backstop = min(sl_backstop, 0.25)
    elif index_name in ['NIFTY', 'FINNIFTY']:
        sl_backstop = min(sl_backstop, 0.25)
        
    # Apply regime-specific target scaling
    if ENABLE_REGIME_SCALING or index_name == 'NIFTY':
        if 'TRENDING' in regime:
            target_pct *= 2.0
        elif regime == 'RANGE_BOUND':
            target_pct *= 0.6

    sl  = ep * (1 - sl_backstop)
    tgt = ep * (1 + target_pct)
    xp  = None; xr = 'EOD'; xt = None

    for _, bar in remaining.iterrows():
        ts   = bar['ts_ist'] if hasattr(bar['ts_ist'], 'hour') else pd.Timestamp(bar['ts_ist'])
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))

        if hhmm >= hard_exit:
            xp = float(bar['close']); xr = 'TIME'; xt = bar['ts_ist']; break
        if lo <= sl:
            xp = sl; xr = 'SL'; xt = bar['ts_ist']; break
        if hi >= tgt:
            xp = tgt; xr = 'TARGET'; xt = bar['ts_ist']; break

    if xp is None:
        last = remaining.iloc[-1] if len(remaining) > 0 else entry_bar
        xp = float(last['close']); xr = 'EOD'; xt = last['ts_ist']
    return max(xp, 0.05), xr, xt

def execute_tsl_idx(entry_bar: pd.Series, remaining: pd.DataFrame, hard_exit: int = 1430, 
                     premium_scale: float = 1.0, regime: str = 'NORMAL', strat_name: str = '',
                     index_name: str = 'NIFTY', is_expiry: bool = False):
    dna = get_index_strategy_dna(index_name, strat_name)
    
    # Cap parameters for option safety to guard against theta decay
    tsl_activate = min(0.06, dna.tsl_activate)
    tsl_trail = min(0.04, dna.tsl_trail)
    target_pct = dna.target_pct
    sl_backstop = dna.sl_backstop
    
    tsl_trail = max(tsl_trail, 0.02)  # Floor to prevent noise stops
    
    is_reversal = 'REVERSAL' in strat_name or 'MEAN' in strat_name or 'BLOCK' in strat_name or 'CRUSH' in strat_name or 'CLIMAX' in strat_name
    is_trend = 'TREND' in strat_name or 'BREAK' in strat_name or 'BURST' in strat_name or 'DRIVE' in strat_name
    
    # Apply standard regime multipliers
    if ENABLE_REGIME_SCALING or index_name == 'NIFTY':
        if 'TRENDING' in regime:
            target_pct *= 2.0
            tsl_activate *= 2.0
            tsl_trail *= 1.5
        elif regime == 'RANGE_BOUND':
            target_pct *= 0.6
            tsl_activate *= 0.6
            tsl_trail *= 0.6
    
    # Handle explosive gap overrides
    if regime == 'EXPLOSIVE_GAP':
        if is_reversal:
            tsl_activate *= 0.6
            tsl_trail *= 0.7
            target_pct *= 0.8
        elif is_trend:
            tsl_activate *= 1.3
            tsl_trail *= 1.2
            target_pct *= 1.5
            
    # Uncapped expiry trails for ZERO_HERO and GAMMA_BLAST on expiry days
    if ENABLE_EXPIRY_UNCAP:
        if is_expiry and (strat_name in ['ZERO_HERO', 'GAMMA_BLAST']):
            target_pct = 999.0
            if not EXPIRY_UNCAP_TIGHT:
                tsl_activate = 0.25
                tsl_trail = 0.15
    
    ep  = float(entry_bar['open'])
    if index_name == 'SENSEX':
        sl_backstop = min(sl_backstop, 0.20)
    elif index_name == 'BANKNIFTY':
        sl_backstop = min(sl_backstop, 0.25)
    elif index_name in ['NIFTY', 'FINNIFTY']:
        sl_backstop = min(sl_backstop, 0.25)
        
    sl  = ep * (1 - sl_backstop)
    tgt = ep * (1 + target_pct)
    thi = ep
    xp = xr = xt = None

    # Spot SL variables
    entry_spot = float(entry_bar['spot'])
    option_type = entry_bar['option_type_flag']
    if option_type == 'CE':
        spot_sl_level = entry_spot * (1.0 - SPOT_SL_PCT)
    else:
        spot_sl_level = entry_spot * (1.0 + SPOT_SL_PCT)

    for _, bar in remaining.iterrows():
        ts   = _get_ts(bar)
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))
        spot = float(bar['spot'])
        thi  = max(thi, hi)

        if hhmm >= hard_exit:
            xp = float(bar['close']); xr = 'TIME'; xt = ts; break
        if lo <= sl:
            xp = sl; xr = 'SL'; xt = ts; break
        if option_type == 'CE' and spot < spot_sl_level:
            xp = float(bar['close']); xr = 'SPOT_SL'; xt = ts; break
        elif option_type == 'PE' and spot > spot_sl_level:
            xp = float(bar['close']); xr = 'SPOT_SL'; xt = ts; break
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
# 10 ENHANCEMENT FILTERS (For signal gating)
# ─────────────────────────────────────────────────────────────────────────────
def volume_spike_filter(c15_slice: pd.DataFrame, min_spike: float = 1.5) -> bool:
    if len(c15_slice) < 3: return True
    avg_volume = c15_slice['volume'].rolling(window=10, min_periods=3).mean().iloc[-1]
    current_volume = c15_slice['volume'].iloc[-1]
    return current_volume >= (avg_volume * min_spike)

def adx_filter(c15_slice: pd.DataFrame, max_adx: float = 25.0) -> bool:
    try:
        high = c15_slice['high']
        low = c15_slice['low']
        close = c15_slice['close']
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14, min_periods=5).mean()
        plus_di = 100 * plus_dm.rolling(window=14, min_periods=5).mean() / atr
        minus_di = 100 * minus_dm.rolling(window=14, min_periods=5).mean() / atr
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(window=14, min_periods=5).mean().iloc[-1]
        return adx < max_adx
    except:
        return True

class PCRHistory:
    def __init__(self, cycles: int = 3):
        self.history = []
        self.cycles = cycles
    def add(self, pcr: float):
        self.history.append(pcr)
        if len(self.history) > self.cycles:
            self.history.pop(0)
    def is_stable(self, threshold: float = 0.15) -> bool:
        if len(self.history) < self.cycles: return True
        variance = max(self.history) - min(self.history)
        avg_pcr = sum(self.history) / len(self.history)
        return (variance / avg_pcr) < threshold if avg_pcr > 0 else True

_pcr_history: Dict[str, PCRHistory] = {}

def get_pcr_history(day: str) -> PCRHistory:
    if day not in _pcr_history:
        _pcr_history[day] = PCRHistory(cycles=3)
    return _pcr_history[day]

def pcr_stability_filter(day: str, pcr: float) -> bool:
    history = get_pcr_history(day)
    history.add(pcr)
    return history.is_stable()

def ema_alignment_filter(c15_slice: pd.DataFrame, direction: str) -> bool:
    try:
        close = c15_slice['close']
        ema9 = close.ewm(span=9, adjust=False).mean().iloc[-1]
        ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
        ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
        if direction == 'CE':
            return ema9 > ema21 > ema50
        else:
            return ema9 < ema21 < ema50
    except:
        return True

def entry_time_filter(hhmm: int, cutoff: int = 1300) -> bool:
    return hhmm < cutoff

def regime_gate_filter(regime: str, blocked_regimes: set) -> bool:
    return regime not in blocked_regimes

def min_premium_filter(real_prem: float, min_required: float) -> bool:
    return real_prem >= min_required

def bb_position_filter(c15_slice: pd.DataFrame, threshold: float = 2.0) -> bool:
    try:
        close = c15_slice['close']
        sma20 = close.rolling(window=20, min_periods=5).mean()
        std20 = close.rolling(window=20, min_periods=5).std()
        upper = sma20 + (std20 * threshold)
        lower = sma20 - (std20 * threshold)
        current = close.iloc[-1]
        upper_val = upper.iloc[-1]
        lower_val = lower.iloc[-1]
        return current >= upper_val or current <= lower_val
    except:
        return True

# ─────────────────────────────────────────────────────────────────────────────
# ENHANCED SIGNAL CHECK WITH ALL FILTERS
# ─────────────────────────────────────────────────────────────────────────────
def signal_check_idx(strat, direction: str, c15_slice, day_ohlc: dict,
                     pcr: float, hhmm: int, expiry: bool,
                     real_prem: float, cfg: IndexConfig, regime: str = 'NORMAL', day: str = '') -> bool:

    # 1. First, check the actual strategy-specific trigger conditions (fixes non-NIFTY breakout bug!)
    ok = signal_check(strat, direction, c15_slice, day_ohlc, pcr, hhmm, expiry, real_prem, cfg)
    if not ok:
        return False

    # 2. Apply the 10 Enhancement Filters
    
    # Remove hardcoded tiered cutoffs and let strategy_dna.json's entry_start / entry_end govern.
        
    # Standard cutoff override for expiry ZERO_HERO/GAMMA_BLAST (can run till 15:00)
    cutoff = strat.entry_end
    if strat.name in {'GAMMA_BLAST', 'ZERO_HERO'} and expiry:
        cutoff = max(cutoff, 1500)
        
    # We apply the general index-level cutoff
    if not entry_time_filter(hhmm, cutoff=cutoff):
        return False
    
    # Reversal Volume check
    REVERSAL_STRATS = {'DAY_LOW_BULLISH', 'DAY_HIGH_BEARISH', 'ULTIMATE_DAY_HIGH_LOW', 
                       'ORDER_BLOCK_REVERSAL', 'MEAN_REVERSION', 'RSI_REVERSAL', 'VOLUME_CLIMAX'}
    if strat.name in REVERSAL_STRATS:
        if not volume_spike_filter(c15_slice, min_spike=1.3):
            return False
    
    # ADX + BB position check for mean reversion
    if strat.name in {'MEAN_REVERSION', 'PREMIUM_CRUSH'}:
        if not adx_filter(c15_slice, max_adx=28):
            return False
        if not bb_position_filter(c15_slice, threshold=1.8):
            return False
    
    # EMA alignment for trend followers
    TREND_FOLLOWERS = {'BEAR_TREND_FOLLOWER', 'BULL_TREND_FOLLOWER', 'TREND_FOLLOWING', 'MOMENTUM_BURST'}
    if strat.name in TREND_FOLLOWERS:
        if not ema_alignment_filter(c15_slice, direction):
            return False
    
    # Regime gate for DAY_HIGH_BEARISH
    if strat.name == 'DAY_HIGH_BEARISH':
        if not regime_gate_filter(regime, blocked_regimes={'TRENDING_BULL'}):
            return False

    return True

# ─────────────────────────────────────────────────────────────────────────────
# SINGLE-INDEX BACKTEST EXECUTION
# ─────────────────────────────────────────────────────────────────────────────
ONE_TRADE_STRATS = {
    'MORNING_BREAKOUT','EARLY_BREAKDOWN','WIDE_RANGE_RIDER',
    'VOLATILITY_BREAKOUT','TREND_FOLLOWING','MEAN_REVERSION',
    'ENHANCED_BULLISH','BEAR_TREND_FOLLOWER','BULL_TREND_FOLLOWER',
    'MAGIC_SQUARE','ORDER_BLOCK_REVERSAL','SHORT_UNWIND','ENHANCED_BEARISH',
}

@dataclass
class Trade:
    date:          object
    strategy:      str
    direction:     str
    regime:        str
    confidence:    float
    lots:          int
    entry_time:    pd.Timestamp
    entry_price:   float
    exit_price:    float
    exit_time:     pd.Timestamp
    exit_reason:   str
    pnl_pts:       float
    pnl_rs:        float
    won:           bool
    armed_reason:  str

def get_base_lots(strat_name: str) -> int:
    tier1 = {'BULL_TREND_FOLLOWER', 'BEAR_TREND_FOLLOWER', 'DAY_LOW_BULLISH', 'DAY_HIGH_BEARISH'}
    tier2 = {'MAGIC_SQUARE', 'WIDE_RANGE_RIDER', 'MEAN_REVERSION', 'ORDER_BLOCK_REVERSAL', 'VOLATILITY_BREAKOUT', 'EARLY_BREAKDOWN', 'MORNING_BREAKOUT'}
    tier3 = {'ENHANCED_BEARISH', 'ENHANCED_BULLISH', 'ULTIMATE_DAY_HIGH_LOW', 'SCALPING', 'OPTIONS_GREEKS', 'AI_ENHANCED', 'BREAKOUT', 'GAMMA_BLAST', 'ZERO_HERO', 'LONG_UNWIND', 'PUT_WRITER_SUPPORT', 'RESIST_BREAK', 'DAY_HIGH_LOW_TRADITIONAL'}
    if strat_name in tier1:
        return 4
    elif strat_name in tier2:
        return 3
    elif strat_name in tier3:
        return 2
    else:
        return 1  # Tier 4 & 5 get 1 lot baseline

def run_index(idx_name: str, opt_data: pd.DataFrame,
              eod_data: pd.DataFrame, cfg: IndexConfig) -> Tuple[List[Trade], str]:

    print(f"  [{idx_name}] Labelling regimes on {opt_data['date'].nunique()} days...", flush=True)
    day_regimes   = label_days(opt_data)
    active_strats = [s for s in make_strategies_v8() if s.name in ACTIVE_STRATEGIES_BY_INDEX.get(idx_name, set())]
    idx_profiles  = INDEX_PROFILES[idx_name]
    trading_days  = sorted(opt_data['date'].unique())
    num_days_limit = os.environ.get("NUM_DAYS_LIMIT")
    if num_days_limit:
        trading_days = trading_days[:int(num_days_limit)]
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

        # Dynamic Strategy Gating: Expiry specialist strategies on expiry day, full hybrid suite on normal days
        if expiry:
            allowed_strategies = {"ZERO_HERO", "GAMMA_BLAST"}
        else:
            allowed_strategies = ACTIVE_STRATEGIES_BY_INDEX.get(idx_name, set())
        active_strats = [s for s in make_strategies_v8() if s.name in allowed_strategies]

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

            # Daily Circuit Breaker check: if closed PnL today <= configured threshold, stop taking entries
            today_pnl = sum(t.pnl_rs for t in all_trades if t.date == day)
            if today_pnl <= DAILY_CIRCUIT_BREAKER_RS:
                break

            # Calculate current concurrent active capital locked in this index
            active_capital = 0.0
            for t in all_trades:
                if t.date == day:
                    if t.entry_time <= ts < t.exit_time:
                        active_capital += t.entry_price * cfg.lot_size * t.lots

            state = compute_intraday_state(c15.iloc[:i+1], pcr)

            for strat in active_strats:
                if strat.name not in idx_profiles:
                    continue

                if hhmm < strat.entry_start or hhmm > strat.entry_end:
                    continue

                # Dynamic strategy regime compatibility check from regime_detector
                from regime_detector import STRATEGY_REGIME_MATRIX
                compat = STRATEGY_REGIME_MATRIX.get(strat.name, {}).get(regime, True)
                if not compat:
                    continue
                if strat.name in ONE_TRADE_STRATS and strat_trades[strat.name] >= 1:
                    continue

                dirs = ['CE','PE'] if strat.direction == 'BOTH' else [strat.direction]

                for direction in dirs:
                    if direction == 'CE' and trades_today['CE'] >= cfg.max_ce_day:
                        continue
                    if direction == 'PE' and trades_today['PE'] >= 15:
                        continue

                    profile = idx_profiles[strat.name]
                    armed, conf, arm_reason = match_profile(profile, ctx, state, direction)
                    if not armed:
                        continue

                    # Threshold check using ENABLE_THRESH_RELAX flag
                    if ENABLE_THRESH_RELAX:
                        dna = get_index_strategy_dna(idx_name, strat.name)
                        min_conf = min(dna.entry_threshold, 0.78)
                    else:
                        min_conf = 0.52

                    if regime == 'EXPLOSIVE_GAP':
                        min_conf_gap = 0.55 if not ENABLE_THRESH_RELAX else max(0.50, min_conf - 0.05)
                        if conf < min_conf_gap:
                            continue
                        conf = min(0.95, conf + 0.08)
                    else:
                        if conf < min_conf:
                            continue

                    opt_b = day_data[
                        (day_data['option_type_flag'] == direction) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] == hhmm)
                    ]
                    if len(opt_b) == 0:
                        continue

                    prem = float(opt_b['close'].iloc[-1])

                    # V14 Premium-Adaptive Sizing (Risk Management)
                    deploy_cap = CAPITAL_PER_INDEX * get_tier_deploy_pct(strat.name)
                    actual_lots = max(1, min(MAX_LOTS_CAP, int(deploy_cap / (prem * cfg.lot_size))))
                    
                    # Strict Concurrent Capital/Margin Gating
                    required_margin = prem * cfg.lot_size * actual_lots
                    if active_capital + required_margin > CAPITAL_PER_INDEX:
                        continue
                    
                    try:
                        ok = signal_check_idx(strat, direction, c15.iloc[:i+1],
                                              day_ohlc, pcr, hhmm, expiry, prem, cfg, 
                                              regime, str(day))
                    except Exception as e:
                        ok = False
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

                    dynamic_exit = get_dynamic_hard_exit(idx_name, strat.name, regime, expiry)
                    fixed_tgt = FIXED_TARGET_STRATEGIES.get(strat.name)
                    if fixed_tgt:
                        xp, xr, xt = execute_fixed_target_idx(entry_bar, remaining, fixed_tgt, dynamic_exit, idx_name, strat.name, regime)
                    else:
                        xp, xr, xt = execute_tsl_idx(entry_bar, remaining, dynamic_exit, cfg.premium_scale, regime, strat.name, idx_name, expiry)

                    slippage = cfg.slippage_pts
                    pnl_pts = xp - entry_price - slippage
                    pnl_rs  = round(pnl_pts * cfg.lot_size * actual_lots - cfg.brokerage, 2)

                    all_trades.append(Trade(
                        date=day, strategy=strat.name, direction=direction,
                        regime=regime, confidence=conf, lots=actual_lots,
                        entry_time=_get_ts(entry_bar),
                        entry_price=entry_price,
                        exit_price=xp, exit_time=xt, exit_reason=xr,
                        pnl_pts=round(pnl_pts, 2), pnl_rs=pnl_rs,
                        won=pnl_rs > 0, armed_reason=arm_reason,
                    ))
                    active_capital += required_margin
                    trades_today[direction] += 1
                    strat_trades[strat.name] += 1
                    break

        if not eod_row.empty:
            prev_close = float(eod_row.iloc[0]['close'])

    print(f"  [{idx_name}] Done — {len(all_trades)} trades", flush=True)
    return all_trades, idx_name

# ─────────────────────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────────────────────
def report_multi(results: Dict[str, List[Trade]], total_days: int):
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
    print(f"BACKTEST V8 AI — MULTI-INDEX SCALE TARGET ({total_days} calendar days)")
    print(f"  4 indices × 36 strategies × Dynamic lot sizing")
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
    print(f"  5% daily target    : {(daily >= CAPITAL * 0.05).sum()} days hit (Rs.{CAPITAL*0.05:,.0f}+)")

    print(f"\n  PER INDEX:")
    hdr = f"  {'Index':<12} {'Trades':>7} {'WR%':>5} {'PnL':>12} {'Days':>6} {'Avg/day':>10} {'Monthly':>10}"
    print(hdr)
    print(f"  {'-'*65}")
    for idx_name in ['NIFTY','BANKNIFTY','FINNIFTY','SENSEX']:
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
    for pct in [0.001, 0.002, 0.005, 0.01, 0.05]:
        thresh = CAPITAL * pct
        label = f"Rs.{thresh:,.0f} ({pct*100:.1f}%)"
        print(f"  Days >= {label:<16}: {(daily>=thresh).sum()}/{udays}")

    print(f"\n  MONTHLY BREAKDOWN:")
    df['month'] = df['date'].dt.to_period('M')
    for m, v in df.groupby('month')['pnl_rs'].sum().items():
        bar  = '#' * min(int(abs(v) / max(1, CAPITAL * 0.01)), 30)
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
    print("BACKTEST V8 AI — SCALING MULTI-STRATEGY ENGINE")
    print("  Dynamic Lot Sizing | 36 Strategies | Parallelized Execution")
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
        out.to_csv('backtest_results/v8_multiindex_trades.csv', index=False)
        print(f"\n  Saved {len(out)} trades -> backtest_results/v8_multiindex_trades.csv")
