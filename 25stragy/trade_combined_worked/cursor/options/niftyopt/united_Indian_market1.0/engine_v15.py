#!/usr/bin/env python3
"""
LIVE PORTFOLIO TRADER — V15 Hybrid Aggressive Multi-Index Production Bot
=======================================================================
Integrates the optimized 5-index sequential portfolio logic into a live paper
trading bot with:
- Warmup data seeding (prior day + current day) for indicator continuity.
- Daily re-authentication and connection resiliency.
- Thread-safe Dhan API throttling wrapper.
- Shared margin pool logic (Rs. 500k capital base).
- Per-index daily circuit breakers (Rs. -10,000 drawdown limit).
- Persistent CSV state logging to survive restarts without state loss.
- Rate-limit friendly caching to prevent API blockages.
- Beautiful, real-time live console status dashboard.
"""

import sys
import os
import json
import time
import math
import logging
import threading
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

# Insert current directory and package path for library imports
sys.path.insert(0, r'C:\cursor\options\niftyopt')
sys.path.insert(0, r'C:\cursor\options\niftyopt\Lib\site-packages')

from dhanhq import dhanhq
from regime_detector import RegimeDetector

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION & CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
CONFIG_PATH = r"C:\25stragy\config_hybrid_aggressive.json"
STRATEGY_DNA_PATH = r"C:\25stragy\strategy_dna.json"
TOKEN_FILE = r"C:\cursor\options\niftyopt\config\dhan_tokens.json"
CLIENT_ID = "1101936133"
TRADE_LOG_FILE = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"

# Ensure data directory exists
os.makedirs(os.path.dirname(TRADE_LOG_FILE), exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(r"C:\cursor\options\niftyopt\data\live_portfolio_trader.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("LivePortfolioTrader")

# ─────────────────────────────────────────────────────────────────────────────
# LOAD STRATEGY AND SYSTEM DATABASES
# ─────────────────────────────────────────────────────────────────────────────
with open(CONFIG_PATH, "r") as f:
    config_db = json.load(f)

with open(STRATEGY_DNA_PATH, "r") as f:
    strategy_db = json.load(f)

CAPITAL_BASE = config_db["system"].get("capital_base", 500000)
CAPITAL_PER_INDEX = config_db["system"].get("capital_per_index", 100000)
GLOBAL_BROKERAGE = config_db["system"].get("global_brokerage", 40.0)
DAILY_CIRCUIT_BREAKER_RS = config_db["system"].get("daily_circuit_breaker_rs", -10000)
SPOT_SL_PCT = config_db["system"].get("spot_sl_pct", 0.0035)

TIER1_DEPLOY_PCT = config_db["system"].get("tier1_deploy_pct", 0.60)
TIER2_DEPLOY_PCT = config_db["system"].get("tier2_deploy_pct", 0.50)
TIER3_DEPLOY_PCT = config_db["system"].get("tier3_deploy_pct", 0.40)
TIER4_DEPLOY_PCT = config_db["system"].get("tier4_deploy_pct", 0.30)
MAX_LOTS_CAP = config_db["system"].get("max_lots_cap", 20)

TIER1_STRATEGIES = set(config_db.get("strategy_tiers", {}).get("tier1", []))
TIER2_STRATEGIES = set(config_db.get("strategy_tiers", {}).get("tier2", []))
TIER3_STRATEGIES = set(config_db.get("strategy_tiers", {}).get("tier3", []))

def get_tier_deploy_pct(strat_name: str) -> float:
    if strat_name in TIER1_STRATEGIES:
        return TIER1_DEPLOY_PCT
    elif strat_name in TIER2_STRATEGIES:
        return TIER2_DEPLOY_PCT
    elif strat_name in TIER3_STRATEGIES:
        return TIER3_DEPLOY_PCT
    else:
        return TIER4_DEPLOY_PCT

# ─────────────────────────────────────────────────────────────────────────────
# DATASTRUCTURES
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class IndexConfig:
    name:          str
    lot_size:      int
    atm_step:      float
    expiry_dow:    int
    security_id:   str
    exchange:      str = 'IDX_I'
    brokerage:     float = 40.0
    premium_scale: float = 1.0
    hard_exit:     int   = 1430
    max_ce_day:    int   = 2
    wide_range_pts: float = 120.0
    entry_cutoff:   int   = 1430
    slippage_pts:   float = 0.5

INDEX_CONFIGS: Dict[str, IndexConfig] = {}
INDEX_TSL_MULTIPLIERS = {}

INDEX_SEC_IDS = {
    'NIFTY': '13',
    'BANKNIFTY': '25',
    'FINNIFTY': '27',
    'MIDCPNIFTY': '442',
    'SENSEX': '51'
}

for idx_name, idx_cfg in config_db["index_profiles"].items():
    sec_id = INDEX_SEC_IDS.get(idx_name, '13')
    INDEX_CONFIGS[idx_name] = IndexConfig(
        name=idx_name,
        lot_size=idx_cfg["lot_size"],
        atm_step=idx_cfg["atm_step"],
        expiry_dow=idx_cfg["expiry_dow"],
        security_id=sec_id,
        exchange='IDX_I',
        brokerage=idx_cfg.get("brokerage", GLOBAL_BROKERAGE),
        premium_scale=idx_cfg.get("premium_scale", 1.0),
        hard_exit=idx_cfg.get("hard_exit", 1430),
        max_ce_day=idx_cfg.get("max_ce_day", 2),
        wide_range_pts=idx_cfg.get("wide_range_pts", 120.0),
        entry_cutoff=idx_cfg.get("entry_cutoff", 1430),
        slippage_pts=idx_cfg.get("slippage_pts", 0.5)
    )
    INDEX_TSL_MULTIPLIERS[idx_name] = idx_cfg.get("tsl_multipliers", {"activate": 1.0, "trail": 0.6, "target": 1.0})

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

def build_dna_matrix() -> Dict[str, IndexStrategyDNA]:
    matrix = {}
    for idx in INDEX_CONFIGS.keys():
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

@dataclass
class StrategyDef:
    name:           str
    direction:      str
    strike:         str
    entry_start:    int
    entry_end:      int
    sl_pct:         float
    target_pct:     float
    tsl_pts:        float
    min_premium:    float
    max_premium:    float
    require_vwap:   bool
    require_volume: bool
    direction_bias: str

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

STRATEGY_DEFS = make_strategies_v8()
ACTIVE_STRATEGIES_BY_INDEX = {}
for idx_name, idx_cfg in config_db["index_profiles"].items():
    ACTIVE_STRATEGIES_BY_INDEX[idx_name] = set(idx_cfg.get("active_strategies", []))

# ─────────────────────────────────────────────────────────────────────────────
# DHAN API CLIENT & THROTTLING
# ─────────────────────────────────────────────────────────────────────────────
_API_LOCK = threading.Lock()
_API_MIN_INTERVAL = 0.50  # Safe 500ms delay between calls
_api_last_call = 0.0

def _api_call(fn, *args, **kwargs):
    """Thread-safe API rate limiter with auto-retry and backoff on 805 rate limits."""
    global _api_last_call
    
    max_retries = 3
    retry_delay = 1.5
    
    for attempt in range(1, max_retries + 1):
        with _API_LOCK:
            now = time.monotonic()
            wait = _API_MIN_INTERVAL - (now - _api_last_call)
            if wait > 0:
                time.sleep(wait)
            
            try:
                result = fn(*args, **kwargs)
                _api_last_call = time.monotonic()
            except Exception as e:
                if attempt == max_retries:
                    raise e
                logger.warning(f"[API_RETRY] Network exception on {fn.__name__ if hasattr(fn, '__name__') else str(fn)}: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
                continue
                
        # Check if result is a rate limit failure
        is_rate_limit = False
        if isinstance(result, dict):
            res_str = str(result)
            if '805' in res_str or 'Too many requests' in res_str:
                is_rate_limit = True
                
        if is_rate_limit:
            if attempt == max_retries:
                logger.error(f"[API_FAILED] Rate limit exceeded after {max_retries} attempts for {fn.__name__ if hasattr(fn, '__name__') else str(fn)}.")
                return result
            logger.warning(f"[RATE_LIMIT] {fn.__name__ if hasattr(fn, '__name__') else str(fn)} returned 805 (Too many requests). Attempt {attempt}/{max_retries}. Retrying in {retry_delay}s...")
            time.sleep(retry_delay)
            retry_delay *= 2.0  # Exponential backoff
            continue
            
        return result

class DhanClientManager:
    def __init__(self):
        self.client = None
        self.connect()

    def connect(self):
        try:
            with open(TOKEN_FILE, 'r') as f:
                tokens = json.load(f)
            access_token = tokens.get('access_token')
            if not access_token:
                raise ValueError("No access_token in token file")
            self.client = dhanhq(CLIENT_ID, access_token)
            logger.info("[SUCCESS] Dhan API client initialized successfully.")
        except Exception as e:
            logger.critical(f"[FAILED] Failed to connect to Dhan API: {e}")
            sys.exit(1)

    def reconnect_if_needed(self):
        """Reload token and reinstantiate client on error."""
        logger.warning("[RECONNECT] Re-authenticating and reloading Dhan client token...")
        self.connect()

dhan_manager = DhanClientManager()

# ─────────────────────────────────────────────────────────────────────────────
# RATE-LIMIT SAFE INDEX STATE CACHE
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class IndexState:
    spot: float = 0.0
    regime: str = "NORMAL"
    pcr: float = 1.0
    last_update: str = "N/A"

index_states: Dict[str, IndexState] = {
    name: IndexState() for name in INDEX_CONFIGS.keys()
}

option_chains_cache: Dict[str, Dict[float, Dict[str, dict]]] = {}
index_candles_1min: Dict[str, pd.DataFrame] = {}


# ─────────────────────────────────────────────────────────────────────────────
# INDICATOR CALCULATIONS
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
    # Filter for today's candles to compute the true intraday VWAP
    today_date = datetime.now().date()
    today_candles = candles15[candles15['timestamp'].dt.date == today_date]
    if len(today_candles) == 0:
        today_candles = candles15  # Fallback
    typ = (today_candles['high'] + today_candles['low'] + today_candles['close']) / 3
    vol = today_candles['volume'].replace(0, 1)
    return float((typ * vol).sum() / vol.sum())

# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL GATING ENHANCEMENT FILTERS
# ─────────────────────────────────────────────────────────────────────────────
def volume_spike_filter(c15_slice: pd.DataFrame, min_spike: float = 1.3) -> bool:
    if len(c15_slice) < 3: return True
    avg_volume = c15_slice['volume'].rolling(window=10, min_periods=3).mean().iloc[-1]
    current_volume = c15_slice['volume'].iloc[-1]
    return current_volume >= (avg_volume * min_spike)

def adx_filter(c15_slice: pd.DataFrame, max_adx: float = 28.0) -> bool:
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

pcr_histories: Dict[str, PCRHistory] = {}

def get_pcr_history(index: str) -> PCRHistory:
    if index not in pcr_histories:
        pcr_histories[index] = PCRHistory(cycles=3)
    return pcr_histories[index]

def pcr_stability_filter(index: str, pcr: float) -> bool:
    history = get_pcr_history(index)
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

def bb_position_filter(c15_slice: pd.DataFrame, threshold: float = 1.8) -> bool:
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
# CORE SIGNAL CHECK
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
        near_vwap = abs(spot - vwap) / vwap < 0.002
        if d == 'CE': return near_vwap and c['close'] > c['open'] and rsi > 50 and ema5 > ema20
        if d == 'PE': return near_vwap and c['close'] < c['open'] and rsi < 50 and ema5 < ema20

    elif n == 'OPENING_DRIVE':
        if len(candles15) < 3: return False
        orb_high_1st = float(candles15.iloc[0]['high'])
        orb_low_1st = float(candles15.iloc[0]['low'])
        if d == 'CE': return spot > orb_high_1st * 1.001 and rsi > 55 and c['close'] > c['open']
        if d == 'PE': return spot < orb_low_1st * 0.999 and rsi < 45 and c['close'] < c['open']

    elif n == 'PREMIUM_CRUSH':
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
            is_squeeze = bb_width < 0.005
            bb_up = bb_mid + 2.0 * bb_std
            bb_dn = bb_mid - 2.0 * bb_std
            if d == 'CE': return is_squeeze and spot > bb_up and rsi > 55
            if d == 'PE': return is_squeeze and spot < bb_dn and rsi < 45

    elif n == 'VOLUME_CLIMAX':
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
        if len(closes) >= 5:
            prev_rsi_2 = calc_rsi(pd.Series(closes[:-2]))
            if d == 'CE': return lows[-1] < lows[-3] and rsi > prev_rsi_2 and c['close'] > c['open']
            if d == 'PE': return highs[-1] > highs[-3] and rsi < prev_rsi_2 and c['close'] < c['open']

    return False

def get_adaptive_engine_regime() -> str:
    """Read the V4 Adaptive Engine's detected regime from JSON config."""
    try:
        config_file = 'adaptive_data/adaptive_config.json'
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config.get('regime', 'NORMAL')
    except Exception as e:
        logger.warning(f"Could not read adaptive engine regime: {e}")
    return 'NORMAL'

# ─────────────────────────────────────────────────────────────────────────────
# INDEX-AWARE SIGNAL CHECK
# ─────────────────────────────────────────────────────────────────────────────
def signal_check_idx(strat: StrategyDef, direction: str, c15_slice: pd.DataFrame, day_ohlc: dict,
                     pcr: float, hhmm: int, expiry: bool,
                     real_prem: float, cfg: IndexConfig, regime: str = 'NORMAL', day_str: str = '') -> bool:

    # V4 Adaptive Engine Regime Filtering
    adaptive_regime = get_adaptive_engine_regime()
    
    if adaptive_regime == 'TRENDING_BEAR':
        # Block counter-trend/mean-reversion bullish strategies
        blocked_bullish_strats = {'DAY_LOW_BULLISH', 'PUT_WRITER_SUPPORT', 'DAY_LOW_BOUNCE'}
        if strat.name in blocked_bullish_strats:
            logger.info(f"[ADAPTIVE FILTER] Blocking {strat.name} ({direction}) due to TRENDING_BEAR regime.")
            return False
        if direction == 'CE' and strat.name in {'ULTIMATE_DAY_HIGH_LOW', 'MEAN_REVERSION', 'RSI_REVERSAL', 'VOLUME_CLIMAX', 'MAGIC_SQUARE'}:
            logger.info(f"[ADAPTIVE FILTER] Blocking CE for {strat.name} due to TRENDING_BEAR regime.")
            return False
            
    elif adaptive_regime == 'TRENDING_BULL':
        # Block counter-trend/mean-reversion bearish strategies
        blocked_bearish_strats = {'DAY_HIGH_BEARISH'}
        if strat.name in blocked_bearish_strats:
            logger.info(f"[ADAPTIVE FILTER] Blocking {strat.name} ({direction}) due to TRENDING_BULL regime.")
            return False
        if direction == 'PE' and strat.name in {'ULTIMATE_DAY_HIGH_LOW', 'MEAN_REVERSION', 'RSI_REVERSAL', 'VOLUME_CLIMAX', 'MAGIC_SQUARE'}:
            logger.info(f"[ADAPTIVE FILTER] Blocking PE for {strat.name} due to TRENDING_BULL regime.")
            return False

    # 1. Base trigger condition
    ok = signal_check(strat, direction, c15_slice, day_ohlc, pcr, hhmm, expiry, real_prem, cfg)
    if not ok:
        return False

    # 2. Gating filters
    cutoff = strat.entry_end
    if strat.name in {'GAMMA_BLAST', 'ZERO_HERO'} and expiry:
        cutoff = max(cutoff, 1500)

    if not entry_time_filter(hhmm, cutoff=cutoff):
        return False

    REVERSAL_STRATS = {'DAY_LOW_BULLISH', 'DAY_HIGH_BEARISH', 'ULTIMATE_DAY_HIGH_LOW', 
                       'ORDER_BLOCK_REVERSAL', 'MEAN_REVERSION', 'RSI_REVERSAL', 'VOLUME_CLIMAX'}
    if strat.name in REVERSAL_STRATS:
        if not volume_spike_filter(c15_slice, min_spike=1.3):
            return False

    if strat.name in {'MEAN_REVERSION', 'PREMIUM_CRUSH'}:
        if not adx_filter(c15_slice, max_adx=28.0):
            return False
        if not bb_position_filter(c15_slice, threshold=1.8):
            return False

    TREND_FOLLOWERS = {'BEAR_TREND_FOLLOWER', 'BULL_TREND_FOLLOWER', 'TREND_FOLLOWING', 'MOMENTUM_BURST'}
    if strat.name in TREND_FOLLOWERS:
        if not ema_alignment_filter(c15_slice, direction):
            return False

    if strat.name == 'DAY_HIGH_BEARISH':
        if not regime_gate_filter(regime, blocked_regimes={'TRENDING_BULL'}):
            return False

    return True

# ─────────────────────────────────────────────────────────────────────────────
# STRIKE PRICE & EXIT PARAMS RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────
def get_numerical_strike(spot: float, strike_str: str, atm_step: float) -> float:
    atm = round(spot / atm_step) * atm_step
    if strike_str == 'ATM':
        return atm
    elif strike_str.startswith('ATM+'):
        offset = int(strike_str.replace('ATM+', ''))
        return atm + offset * atm_step
    elif strike_str.startswith('ATM-'):
        offset = int(strike_str.replace('ATM-', ''))
        return atm - offset * atm_step
    return atm

def resolve_target_strike(direction: str, strike_str: str, expiry: bool, strat_name: str) -> str:
    target = strike_str
    if expiry and strat_name == 'ZERO_HERO':
        target = 'ATM+3'
    elif expiry and strat_name == 'GAMMA_BLAST':
        target = 'ATM+2'
    
    if direction == 'PE':
        if target.startswith('ATM+'):
            target = target.replace('ATM+', 'ATM-')
        elif target.startswith('ATM-'):
            target = target.replace('ATM-', 'ATM+')
    return target

def get_dynamic_hard_exit(index: str, strategy: str, regime: str, is_expiry: bool) -> int:
    is_reversal = any(x in strategy for x in ['REVERSAL', 'MEAN', 'BLOCK', 'CRUSH', 'CLIMAX', 'LOW_BULLISH', 'HIGH_BEARISH'])
    if is_expiry:
        return 1245 if is_reversal else 1330
    if regime in ['TRENDING_BULL', 'TRENDING_BEAR', 'EXPLOSIVE_GAP']:
        return 1330 if is_reversal else 1430
    return 1300 if is_reversal else 1430

# ─────────────────────────────────────────────────────────────────────────────
# TRADING STATE MANAGEMENT & CSV STORAGE
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Trade:
    index: str
    strategy: str
    direction: str
    strike: float
    option_name: str
    lots: int
    entry_time: str
    entry_price: float
    entry_spot: float
    highest_premium: float
    spot_sl_level: float
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    exit_reason: Optional[str] = None
    pnl_rs: Optional[float] = None
    status: str = 'OPEN'
    regime: str = 'NORMAL'
    option_security_id: Optional[str] = None

active_trades: List[Trade] = []
completed_trades: List[Trade] = []

def load_trade_state_from_csv():
    global active_trades, completed_trades
    active_trades = []
    completed_trades = []
    if not os.path.exists(TRADE_LOG_FILE):
        return
    try:
        df = pd.read_csv(TRADE_LOG_FILE)
        today_str = datetime.now().strftime('%Y-%m-%d')
        for _, row in df.iterrows():
            t_entry = row['entry_time']
            if not t_entry.startswith(today_str):
                continue  # Skip historical days
            
            trade = Trade(
                index=row['index'],
                strategy=row['strategy'],
                direction=row['direction'],
                strike=float(row['strike']),
                option_name=row['option_name'],
                lots=int(row['lots']),
                entry_time=row['entry_time'],
                entry_price=float(row['entry_price']),
                entry_spot=float(row['entry_spot']),
                highest_premium=float(row['highest_premium']),
                spot_sl_level=float(row['spot_sl_level']),
                exit_price=float(row['exit_price']) if pd.notna(row['exit_price']) else None,
                exit_time=row['exit_time'] if pd.notna(row['exit_time']) else None,
                exit_reason=row['exit_reason'] if pd.notna(row['exit_reason']) else None,
                pnl_rs=float(row['pnl_rs']) if pd.notna(row['pnl_rs']) else None,
                status=row['status'],
                regime=row['regime'],
                option_security_id=str(row['option_security_id']) if 'option_security_id' in row and pd.notna(row['option_security_id']) else None
            )
            if trade.status == 'OPEN':
                active_trades.append(trade)
            else:
                completed_trades.append(trade)
        logger.info(f"Loaded {len(active_trades)} active trades & {len(completed_trades)} completed trades from CSV.")
    except Exception as e:
        logger.error(f"Error loading trade state from CSV: {e}")

def save_trade_state_to_csv():
    try:
        all_tr = active_trades + completed_trades
        records = []
        for t in all_tr:
            records.append({
                'index': t.index,
                'strategy': t.strategy,
                'direction': t.direction,
                'strike': t.strike,
                'option_name': t.option_name,
                'lots': t.lots,
                'entry_time': t.entry_time,
                'entry_price': t.entry_price,
                'entry_spot': t.entry_spot,
                'highest_premium': t.highest_premium,
                'spot_sl_level': t.spot_sl_level,
                'exit_price': t.exit_price,
                'exit_time': t.exit_time,
                'exit_reason': t.exit_reason,
                'pnl_rs': t.pnl_rs,
                'status': t.status,
                'regime': t.regime,
                'option_security_id': t.option_security_id
            })
        df = pd.DataFrame(records)
        df.to_csv(TRADE_LOG_FILE, index=False)
    except Exception as e:
        logger.error(f"Error saving trade state to CSV: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# DATA SEEDING & RESAMPLING WARMUP
# ─────────────────────────────────────────────────────────────────────────────
cached_expiries: Dict[str, str] = {}
regime_detectors: Dict[str, RegimeDetector] = {}

def fetch_index_warmup_candles(idx_cfg: IndexConfig) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch 1-min index spot bars for prior trading day and current day."""
    today = datetime.now()
    start_date = (today - timedelta(days=5)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')

    r = _api_call(
        dhan_manager.client.intraday_minute_data,
        security_id=idx_cfg.security_id,
        exchange_segment=idx_cfg.exchange,
        instrument_type='INDEX',
        from_date=start_date,
        to_date=end_date,
        interval=1
    )

    if not r or r.get('status') != 'success':
        raise ValueError(f"Failed to fetch historical minutes for {idx_cfg.name}: {r}")

    df = pd.DataFrame(r['data'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
    df = df.set_index('timestamp').sort_index()

    # Split into dates
    unique_dates = sorted(list(set(df.index.date)))
    today_date = today.date()

    # Identify prior day and today
    today_df = df[df.index.date == today_date]
    prior_days = [d for d in unique_dates if d < today_date]

    if not prior_days:
        prior_day_date = unique_dates[-1]
        prior_df = df[df.index.date == prior_day_date]
        today_df = pd.DataFrame()
    else:
        prior_day_date = prior_days[-1]
        prior_df = df[df.index.date == prior_day_date]

    return prior_df, today_df

def resample_1min_to_15min(df_1min: pd.DataFrame) -> pd.DataFrame:
    r_open   = df_1min['open'].resample('15min').first()
    r_high   = df_1min['high'].resample('15min').max()
    r_low    = df_1min['low'].resample('15min').min()
    r_close  = df_1min['close'].resample('15min').last()
    r_volume = df_1min['volume'].resample('15min').sum()

    c15 = pd.DataFrame({
        'open': r_open,
        'high': r_high,
        'low': r_low,
        'close': r_close,
        'volume': r_volume
    }).dropna(subset=['close']).reset_index()
    
    if 'index' in c15.columns:
        c15 = c15.rename(columns={'index': 'timestamp'})
        
    c15['hhmm'] = c15['timestamp'].dt.hour * 100 + c15['timestamp'].dt.minute
    return c15

# ─────────────────────────────────────────────────────────────────────────────
# WARMUP ROUTINE
# ─────────────────────────────────────────────────────────────────────────────
def perform_data_warmup():
    global index_candles_1min, option_chains_cache
    logger.info("[WARMUP] Executing pre-market seeding and indicator warmup...")
    for idx_name, idx_cfg in INDEX_CONFIGS.items():
        logger.info(f"Warming up {idx_name}...")
        
        # 1. Fetch expiries
        exp_r = _api_call(dhan_manager.client.expiry_list, under_security_id=int(idx_cfg.security_id), under_exchange_segment='IDX_I')
        if exp_r and exp_r.get('status') == 'success':
            expiries = exp_r.get('data', {}).get('data', [])
            if expiries:
                cached_expiries[idx_name] = expiries[0]
                logger.info(f"  {idx_name} Expiry Selected: {expiries[0]}")
            else:
                raise ValueError(f"No expiries returned for {idx_name}")
        else:
            raise ValueError(f"Failed to fetch expiry list for {idx_name}: {exp_r}")

        # 2. Fetch warmup candles
        prior_df, today_df = fetch_index_warmup_candles(idx_cfg)
        
        # Cache initial 1-minute combined candles
        df_combined = pd.concat([prior_df, today_df]) if len(today_df) > 0 else prior_df
        index_candles_1min[idx_name] = df_combined
        
        # 3. Cache initial option chain and compute initial PCR
        try:
            chain = fetch_and_parse_option_chain(idx_cfg, expiries[0])
            option_chains_cache[idx_name] = chain
            put_oi = sum(chain[s]['PE']['oi'] for s in chain if 'PE' in chain[s])
            call_oi = sum(chain[s]['CE']['oi'] for s in chain if 'CE' in chain[s])
            pcr = put_oi / call_oi if call_oi > 0 else 1.0
            index_states[idx_name].pcr = pcr
        except Exception as e:
            logger.warning(f"  Could not cache initial option chain for {idx_name}: {e}. Will retry in round-robin.")
            option_chains_cache[idx_name] = {}
            index_states[idx_name].pcr = 1.0

        # Initialize regime detector
        detector = RegimeDetector()
        regime_detectors[idx_name] = detector
        
        # Initialize regime detector with today's minutes if any exist
        if len(today_df) > 0:
            detector.new_day(today_df['open'].iloc[0])
            for ts, row in today_df.iterrows():
                hhmm = ts.hour * 100 + ts.minute
                detector.update(row['close'], iv=0.0, hhmm=hhmm)
            spot_px = today_df['close'].iloc[-1]
        else:
            detector.new_day(prior_df['open'].iloc[0])
            spot_px = prior_df['close'].iloc[-1]
            
        # Seed cache
        index_states[idx_name].spot = spot_px
        index_states[idx_name].regime = detector.snapshot().regime
        index_states[idx_name].last_update = datetime.now().strftime('%H:%M:%S')
        logger.info(f"  {idx_name} successfully warmed up. Spot: {spot_px} | Regime: {index_states[idx_name].regime} | PCR: {index_states[idx_name].pcr:.2f}")

# ─────────────────────────────────────────────────────────────────────────────
# OPTION CHAIN RETRIEVAL & PARSING
# ─────────────────────────────────────────────────────────────────────────────
def fetch_and_parse_option_chain(idx_cfg: IndexConfig, expiry: str) -> Dict[float, Dict[str, dict]]:
    oc = _api_call(
        dhan_manager.client.option_chain,
        under_security_id=int(idx_cfg.security_id),
        under_exchange_segment='IDX_I',
        expiry=expiry
    )
    if not oc or oc.get('status') != 'success':
        raise ValueError(f"Failed to fetch option chain for {idx_cfg.name}: {oc}")
        
    parsed = {}
    data = oc.get('data', {})
    oc_dict = data.get('oc', {})
    if not oc_dict:
        oc_dict = data.get('data', {}).get('oc', {})

    for strike_str, strike_data in oc_dict.items():
        try:
            strike = float(strike_str)
        except ValueError:
            continue
        parsed[strike] = {}
        for side in ['ce', 'pe']:
            contract = strike_data.get(side)
            if contract:
                parsed[strike][side.upper()] = {
                    'security_id': str(contract.get('security_id', '')),
                    'ltp': float(contract.get('last_price', 0.0) or 0.0),
                    'bid': float(contract.get('top_bid_price', 0.0) or 0.0),
                    'ask': float(contract.get('top_ask_price', 0.0) or 0.0),
                    'oi': int(contract.get('oi', 0) or 0),
                    'volume': int(contract.get('volume', 0) or 0),
                    'iv': float(contract.get('implied_volatility', 0.0) or 0.0),
                    'greeks': contract.get('greeks', {}),
                    'trading_symbol': contract.get('trading_symbol', f"{idx_cfg.name} {expiry} {strike} {side.upper()}")
                }
    return parsed

# ─────────────────────────────────────────────────────────────────────────────
# TRADING ENGINE LOOPS
# ─────────────────────────────────────────────────────────────────────────────
def get_shared_active_margin() -> float:
    margin = 0.0
    for t in active_trades:
        idx_cfg = INDEX_CONFIGS[t.index]
        margin += t.entry_price * idx_cfg.lot_size * t.lots
    return margin

def get_today_realized_pnl(index_name: str) -> float:
    return sum(t.pnl_rs for t in completed_trades if t.index == index_name)

def update_active_trades_exits(now_time: datetime):
    """Scan all active open trades and evaluate exits (SL, TSL, SPOT_SL, TARGET, TIME)."""
    global active_trades, completed_trades
    
    if not active_trades:
        return

    current_hhmm = now_time.hour * 100 + now_time.minute
    
    # Group active trades by segment to query ticker data
    nse_fno_ids = []
    bse_fno_ids = []
    legacy_trades = []
    
    for t in active_trades:
        if not t.option_security_id:
            legacy_trades.append(t)
        else:
            sec_id = int(t.option_security_id)
            if t.index == 'SENSEX':
                bse_fno_ids.append(sec_id)
            else:
                nse_fno_ids.append(sec_id)
                
    ticker_prices = {}
    
    # Query ticker_data for active trade options
    if nse_fno_ids or bse_fno_ids:
        try:
            sec_dict = {}
            if nse_fno_ids:
                sec_dict['NSE_FNO'] = nse_fno_ids
            if bse_fno_ids:
                sec_dict['BSE_FNO'] = bse_fno_ids
                
            tick_res = _api_call(dhan_manager.client.ticker_data, securities=sec_dict)
            if tick_res and tick_res.get('status') == 'success':
                data_map = tick_res.get('data', {}).get('data', {})
                for sec_id, sec_data in data_map.get('NSE_FNO', {}).items():
                    ticker_prices[str(sec_id)] = float(sec_data.get('last_price', 0.0) or 0.0)
                for sec_id, sec_data in data_map.get('BSE_FNO', {}).items():
                    ticker_prices[str(sec_id)] = float(sec_data.get('last_price', 0.0) or 0.0)
        except Exception as e:
            logger.error(f"Error fetching option tickers for exit tracking: {e}")
            
    # Resolve any legacy open trades that don't have option_security_id in CSV yet
    if legacy_trades:
        indices_to_fetch = set(t.index for t in legacy_trades)
        chains_by_idx = {}
        for idx_name in indices_to_fetch:
            try:
                expiry = cached_expiries[idx_name]
                chains_by_idx[idx_name] = fetch_and_parse_option_chain(INDEX_CONFIGS[idx_name], expiry)
            except Exception as e:
                logger.error(f"Error fetching option chain for legacy exit tracking on {idx_name}: {e}")
                
        for t in legacy_trades:
            chain = chains_by_idx.get(t.index, {})
            side = t.direction.upper()
            contract = chain.get(t.strike, {}).get(side)
            if contract and contract.get('security_id'):
                t.option_security_id = str(contract['security_id'])
                save_trade_state_to_csv()
                ticker_prices[t.option_security_id] = contract['ltp']
                logger.info(f"Resolved option security ID for legacy trade {t.option_name}: {t.option_security_id}")

    # Copy list to iterate safely
    for trade in list(active_trades):
        idx_cfg = INDEX_CONFIGS[trade.index]
        
        # 1. Get spot price from live cache
        spot = index_states[trade.index].spot or trade.entry_spot
        
        # 2. Get option contract price
        current_ltp = 0.0
        if trade.option_security_id:
            current_ltp = ticker_prices.get(str(trade.option_security_id), 0.0)
            
        if current_ltp <= 0.0:
            # Fallback to local option chain cache
            chain = option_chains_cache.get(trade.index, {})
            contract = chain.get(trade.strike, {}).get(trade.direction.upper())
            if contract:
                current_ltp = contract['ltp']
                
        if current_ltp <= 0.0:
            logger.warning(f"Could not resolve price for active trade {trade.option_name}. Skipping this cycle.")
            continue
            
        # Update highest premium seen
        trade.highest_premium = max(trade.highest_premium, current_ltp)
        
        # 3. Resolve exit parameters
        expiry_day = (now_time.weekday() == idx_cfg.expiry_dow)
        dna = get_index_strategy_dna(trade.index, trade.strategy)
        
        is_expiry_special = expiry_day and (trade.strategy in ['ZERO_HERO', 'GAMMA_BLAST'])
        if is_expiry_special:
            tsl_activate = 4.0
            tsl_trail = 0.50
            target_pct = 999.0
        else:
            tsl_activate = min(0.06, dna.tsl_activate)
            tsl_trail = min(0.04, dna.tsl_trail)
            target_pct = dna.target_pct
            tsl_trail = max(tsl_trail, 0.02)
            
        regime = trade.regime
        if trade.index == 'NIFTY':
            if 'TRENDING' in regime:
                mult = 2.5 if trade.strategy in ['MOMENTUM_BURST', 'MACD_DIVERGENCE'] else 2.0
                target_pct *= mult
                tsl_activate *= 2.0
                tsl_trail *= 1.5
            elif regime == 'RANGE_BOUND':
                target_pct *= 0.6
                tsl_activate *= 0.6
                tsl_trail *= 0.6
                
        if expiry_day and (trade.strategy in ['ZERO_HERO', 'GAMMA_BLAST']):
            target_pct = 999.0
            
        hard_exit_time = get_dynamic_hard_exit(trade.index, trade.strategy, regime, expiry_day)
        
        sl_backstop = dna.sl_backstop
        if trade.index == 'SENSEX':
            sl_backstop = min(sl_backstop, 0.20)
        else:
            sl_backstop = min(sl_backstop, 0.25)
            
        sl_price = trade.entry_price * (1 - sl_backstop)
        target_price = trade.entry_price * (1 + target_pct)
        
        exit_triggered = False
        reason = ""
        exit_price = current_ltp
        
        # 4. Check conditions
        if current_hhmm >= hard_exit_time:
            exit_triggered = True
            reason = "TIME"
        elif current_ltp <= sl_price:
            exit_triggered = True
            reason = "SL"
            exit_price = sl_price
        elif trade.direction == 'CE' and spot < trade.spot_sl_level:
            exit_triggered = True
            reason = "SPOT_SL"
        elif trade.direction == 'PE' and spot > trade.spot_sl_level:
            exit_triggered = True
            reason = "SPOT_SL"
        elif current_ltp >= target_price:
            exit_triggered = True
            reason = "TARGET"
            exit_price = target_price
        elif trade.highest_premium >= trade.entry_price * (1 + tsl_activate):
            tsl_floor = trade.highest_premium * (1 - tsl_trail)
            if current_ltp <= tsl_floor:
                exit_triggered = True
                reason = "TSL"
                exit_price = max(tsl_floor, sl_price)
                
        # 5. Execute exit
        if exit_triggered:
            trade.exit_price = round(exit_price, 2)
            trade.exit_time = now_time.strftime('%Y-%m-%d %H:%M:%S')
            trade.exit_reason = reason
            
            pnl_pts = trade.exit_price - trade.entry_price - idx_cfg.slippage_pts
            trade.pnl_rs = round(pnl_pts * idx_cfg.lot_size * trade.lots - idx_cfg.brokerage, 2)
            trade.status = 'CLOSED'
            
            active_trades.remove(trade)
            completed_trades.append(trade)
            save_trade_state_to_csv()
            logger.info(f"[EXIT] CLOSED {trade.index} {trade.strategy} ({trade.direction}) | Reason: {reason} | Entry: {trade.entry_price} | Exit: {trade.exit_price} | PnL: Rs. {trade.pnl_rs}")

def run_candle_boundary_scan(now_time: datetime):
    """Triggered on 1-minute boundaries. Runs entry signal scans using cached spot candles and option chains."""
    global active_trades
    
    current_hhmm = now_time.hour * 100 + now_time.minute
    logger.info(f"[SCAN] Starting 1-minute candle scan at {now_time.strftime('%H:%M:%S')} (hhmm={current_hhmm})")
    
    for idx_name, idx_cfg in INDEX_CONFIGS.items():
        realized_pnl = get_today_realized_pnl(idx_name)
        if realized_pnl <= DAILY_CIRCUIT_BREAKER_RS:
            logger.warning(f"  {idx_name}: Skipped (Index Daily Drawdown Circuit Breaker active: PnL = Rs. {realized_pnl})")
            continue
            
        try:
            # 1. Get cached 1-minute candles
            df_combined = index_candles_1min.get(idx_name)
            if df_combined is None or len(df_combined) < 5:
                continue
                
            # 2. Resample to 15-minute candles
            c15 = resample_1min_to_15min(df_combined)
            if len(c15) < 4:
                continue
                
            # Extract day OHLC from today's candles
            today_date = now_time.date()
            today_df = df_combined[df_combined.index.date == today_date]
            if len(today_df) == 0:
                continue
                
            day_ohlc = {
                'open': today_df['open'].iloc[0],
                'high': today_df['high'].max(),
                'low': today_df['low'].min(),
                'close': today_df['close'].iloc[-1]
            }
            spot = day_ohlc['close']
            
            # 3. Update Regime Detector
            detector = regime_detectors[idx_name]
            detector.new_day(day_ohlc['open'])
            for ts, row in today_df.iterrows():
                h_m = ts.hour * 100 + ts.minute
                detector.update(row['close'], iv=0.0, hhmm=h_m)
                
            regime = detector.snapshot().regime
            expiry_day = (now_time.weekday() == idx_cfg.expiry_dow)
            
            # Update cache states
            index_states[idx_name].spot = spot
            index_states[idx_name].regime = regime
            
            # 4. Get cached option chain & PCR
            chain = option_chains_cache.get(idx_name)
            if not chain:
                continue
                
            pcr = index_states[idx_name].pcr
            
            # 5. Evaluate strategies
            allowed_strategies = ACTIVE_STRATEGIES_BY_INDEX.get(idx_name, set())
            
            for strat in STRATEGY_DEFS:
                if strat.name not in allowed_strategies:
                    continue
                    
                done_today = sum(1 for t in (active_trades + completed_trades) if t.index == idx_name and t.strategy == strat.name)
                dna = get_index_strategy_dna(idx_name, strat.name)
                if done_today >= dna.max_trades_per_day:
                    continue
                    
                directions = []
                if strat.direction == 'BOTH':
                    directions = ['CE', 'PE']
                else:
                    directions = [strat.direction]
                    
                for direction in directions:
                    if strat.direction_bias and direction != strat.direction_bias:
                        continue
                        
                    target_strike_str = resolve_target_strike(direction, strat.strike, expiry_day, strat.name)
                    num_strike = get_numerical_strike(spot, target_strike_str, idx_cfg.atm_step)
                    
                    contract = chain.get(num_strike, {}).get(direction)
                    if not contract:
                        continue
                    
                    real_prem = contract['ask']
                    if real_prem <= 0:
                        continue
                        
                    ok = signal_check_idx(
                        strat=strat,
                        direction=direction,
                        c15_slice=c15,
                        day_ohlc=day_ohlc,
                        pcr=pcr,
                        hhmm=current_hhmm,
                        expiry=expiry_day,
                        real_prem=real_prem,
                        cfg=idx_cfg,
                        regime=regime,
                        day_str=now_time.strftime('%Y-%m-%d')
                    )
                    
                    if not ok:
                        continue
                        
                    # Calculate active margin specifically for this index
                    idx_margin_used = sum(t.entry_price * INDEX_CONFIGS[t.index].lot_size * t.lots for t in active_trades if t.index == idx_name)
                    idx_avail_capital = max(0.0, CAPITAL_PER_INDEX - idx_margin_used)
                    
                    # Also respect overall shared capital base availability
                    margin_used = get_shared_active_margin()
                    avail_capital = max(0.0, CAPITAL_BASE - margin_used)
                    
                    # Deploy cap for this trade is scaled based on CAPITAL_PER_INDEX
                    deploy_cap = CAPITAL_PER_INDEX * get_tier_deploy_pct(strat.name)
                    deploy_cap = min(deploy_cap, idx_avail_capital, avail_capital)
                    
                    actual_lots = max(1, min(MAX_LOTS_CAP, int(deploy_cap / (real_prem * idx_cfg.lot_size))))
                    required_margin = real_prem * idx_cfg.lot_size * actual_lots
                    
                    if (idx_margin_used + required_margin > CAPITAL_PER_INDEX) or (margin_used + required_margin > CAPITAL_BASE):
                        logger.warning(f"  {idx_name} {strat.name} ({direction}): Triggered but skipped due to capital constraint (Required: Rs. {required_margin:.0f}, Index Avail: Rs. {idx_avail_capital:.0f}, Global Avail: Rs. {avail_capital:.0f})")
                        continue
                        
                    if direction == 'CE':
                        spot_sl_level = spot * (1.0 - SPOT_SL_PCT)
                    else:
                        spot_sl_level = spot * (1.0 + SPOT_SL_PCT)
                        
                    new_trade = Trade(
                        index=idx_name,
                        strategy=strat.name,
                        direction=direction,
                        strike=num_strike,
                        option_name=contract['trading_symbol'],
                        lots=actual_lots,
                        entry_time=now_time.strftime('%Y-%m-%d %H:%M:%S'),
                        entry_price=real_prem,
                        entry_spot=spot,
                        highest_premium=real_prem,
                        spot_sl_level=round(spot_sl_level, 2),
                        regime=regime,
                        option_security_id=str(contract.get('security_id', ''))
                    )
                    active_trades.append(new_trade)
                    save_trade_state_to_csv()
                    logger.info(f"[ENTRY] ENTERED {idx_name} {strat.name} ({direction}) | Strike: {num_strike} | Premium: Rs. {real_prem} | Lots: {actual_lots} | Margin: Rs. {required_margin:.0f} | Spot: {spot}")
                    
        except Exception as e:
            logger.error(f"Error scanning index {idx_name}: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# LIVE CONSOLE DASHBOARD (0 API CALLS)
# ─────────────────────────────────────────────────────────────────────────────
def print_dashboard(now_time: datetime):
    try:
        states_dict = {}
        for idx_name in INDEX_CONFIGS.keys():
            state = index_states[idx_name]
            states_dict[idx_name] = {
                "spot": state.spot,
                "regime": state.regime,
                "pcr": state.pcr,
                "expiry_date": cached_expiries.get(idx_name, "N/A"),
                "last_update": state.last_update
            }
        # Save to shared file
        with open(r"C:\cursor\options\niftyopt\data\live_index_states.json", "w") as f_json:
            json.dump(states_dict, f_json, indent=2)
    except Exception as e:
        logger.warning(f"Error saving index states JSON: {e}")

    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("=" * 100)
    print(f" LIVE PORTFOLIO PAPER TRADER (V15 Hybrid Aggressive) - {now_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    
    margin_used = get_shared_active_margin()
    avail_cap = CAPITAL_BASE - margin_used
    total_realized = sum(t.pnl_rs for t in completed_trades)
    
    print(f" CAPITAL BASE    : Rs. {CAPITAL_BASE:,.2f}")
    print(f" USED MARGIN     : Rs. {margin_used:,.2f}")
    print(f" AVAILABLE CAP   : Rs. {avail_cap:,.2f}")
    print(f" TODAY'S NET PNL : Rs. {total_realized:,.2f}")
    print("-" * 100)
    
    # Indices Status (Uses cache - 0 API calls)
    print(f" {'Index':<12} | {'Spot Price':<10} | {'Regime':<15} | {'Expiry Date':<12} | {'PCR':<6} | {'Today PnL':<12} | {'Last Update'}")
    print("-" * 100)
    for idx_name in INDEX_CONFIGS.keys():
        state = index_states[idx_name]
        exp_date = cached_expiries.get(idx_name, "N/A")
        idx_pnl = get_today_realized_pnl(idx_name)
        print(f" {idx_name:<12} | {state.spot:<10.2f} | {state.regime:<15} | {exp_date:<12} | {state.pcr:<6.2f} | Rs. {idx_pnl:<10.2f} | {state.last_update}")
        
    print("=" * 100)
    # Active Trades Table
    print(f" ACTIVE POSITIONS ({len(active_trades)})")
    print("-" * 100)
    print(f" {'Index':<10} | {'Strategy':<20} | {'Dir':<3} | {'Lots':<4} | {'Entry Px':<8} | {'Highest Px':<10} | {'Spot':<9} | {'Spot SL':<9} | {'Unrealized'}")
    print("-" * 100)
    for t in active_trades:
        unrealized_rs = (t.highest_premium - t.entry_price) * INDEX_CONFIGS[t.index].lot_size * t.lots
        print(f" {t.index:<10} | {t.strategy:<20} | {t.direction:<3} | {t.lots:<4} | {t.entry_price:<8.2f} | {t.highest_premium:<10.2f} | {t.entry_spot:<9.2f} | {t.spot_sl_level:<9.2f} | Rs. {unrealized_rs:<10.2f}")
        
    print("=" * 100)
    # Completed Trades Table (Shows last 6)
    print(f" COMPLETED TRADES ({len(completed_trades)})")
    print("-" * 100)
    print(f" {'Index':<10} | {'Strategy':<20} | {'Dir':<3} | {'Entry Px':<8} | {'Exit Px':<8} | {'Exit Time':<8} | {'Reason':<10} | {'PnL (Rs.)'}")
    print("-" * 100)
    for t in completed_trades[-6:]:
        exit_t_short = t.exit_time.split(' ')[1] if t.exit_time else "N/A"
        print(f" {t.index:<10} | {t.strategy:<20} | {t.direction:<3} | {t.entry_price:<8.2f} | {t.exit_price:<8.2f} | {exit_t_short:<8} | {t.exit_reason:<10} | Rs. {t.pnl_rs:<10.2f}")
        
    print("=" * 100)
    print(" Press Ctrl+C to stop trading safely.")
    print("=" * 100)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def main():
    logger.info("Initializing Live Portfolio Trader Bot...")
    
    # 1. Load persistent trade state from CSV (resiliency check)
    load_trade_state_from_csv()
    
    # 2. Perform warmup
    perform_data_warmup()
    
    logger.info("Bot is active and running. Waiting for trading hours...")
    
    # 3. Initialize boundary parameters
    now = datetime.now()
    last_scanned_minute = now.minute
    
    while True:
        try:
            now = datetime.now()
            current_time_num = now.hour * 100 + now.minute
            
            # Pre-market wait (before 9:15 AM)
            if current_time_num < 915:
                print(f"Waiting for market open. Current time: {now.strftime('%H:%M:%S')}", end='\r')
                time.sleep(1)
                continue
                
            # Post-market exit (after 3:30 PM)
            if current_time_num >= 1530:
                logger.info("Market is closed. Shutting down trading engine for the day.")
                if active_trades:
                    logger.info("Closing all remaining open trades at EOD...")
                    update_active_trades_exits(now)
                try:
                    logger.info("Running automated EOD performance & learning log audit...")
                    from EOD_ANALYSIS_REPORT import run_eod_analysis
                    run_eod_analysis(now.strftime("%Y-%m-%d"))
                except Exception as e:
                    logger.error(f"Failed to compile automated EOD report: {e}")
                break
                
            # Fetch live spot prices for all 5 indices in one call
            try:
                sec_dict = {'IDX_I': [13, 25, 27, 51, 442]}
                tick_res = _api_call(dhan_manager.client.ticker_data, securities=sec_dict)
                if tick_res and tick_res.get('status') == 'success':
                    data_map = tick_res.get('data', {}).get('data', {}).get('IDX_I', {})
                    for idx_name, idx_cfg in INDEX_CONFIGS.items():
                        sec_data = data_map.get(str(idx_cfg.security_id))
                        if sec_data:
                            lp = float(sec_data.get('last_price', 0.0) or 0.0)
                            if lp > 0:
                                index_states[idx_name].spot = lp
                                index_states[idx_name].last_update = now.strftime('%H:%M:%S')
                                
                                # Update 1-minute local candle cache
                                df = index_candles_1min.get(idx_name)
                                if df is not None:
                                    now_minute_ts = now.replace(second=0, microsecond=0)
                                    if now_minute_ts in df.index:
                                        df.at[now_minute_ts, 'close'] = lp
                                        df.at[now_minute_ts, 'high'] = max(df.at[now_minute_ts, 'high'], lp)
                                        df.at[now_minute_ts, 'low'] = min(df.at[now_minute_ts, 'low'], lp)
                                    else:
                                        # Create new minute bar
                                        new_row = pd.DataFrame([{
                                            'open': lp, 'high': lp, 'low': lp, 'close': lp, 'volume': 0
                                        }], index=[now_minute_ts])
                                        new_row.index.name = 'timestamp'
                                        index_candles_1min[idx_name] = pd.concat([df, new_row])
            except Exception as e:
                logger.warning(f"Error fetching live ticker spot prices: {e}")

            # A. Exit Tracking Loop (Runs every 10 seconds)
            if active_trades:
                update_active_trades_exits(now)
            
            # B. 1-Minute Entry Scanning Loop (Evaluates every 1 minute on change)
            current_minute_boundary = now.minute
            if current_minute_boundary != last_scanned_minute:
                # Wait 5 seconds into the minute to ensure underlying candles update
                if now.second >= 5:
                    # 1. Round-robin option chain & PCR refresh (exactly 1 API call per minute)
                    indices_list = list(INDEX_CONFIGS.keys())
                    refresh_idx_name = indices_list[current_minute_boundary % len(indices_list)]
                    try:
                        expiry_date = cached_expiries[refresh_idx_name]
                        chain = fetch_and_parse_option_chain(INDEX_CONFIGS[refresh_idx_name], expiry_date)
                        if chain:
                            option_chains_cache[refresh_idx_name] = chain
                            put_oi = sum(chain[s]['PE']['oi'] for s in chain if 'PE' in chain[s])
                            call_oi = sum(chain[s]['CE']['oi'] for s in chain if 'CE' in chain[s])
                            pcr = put_oi / call_oi if call_oi > 0 else 1.0
                            index_states[refresh_idx_name].pcr = pcr
                    except Exception as e:
                        logger.error(f"Error refreshing option chain for {refresh_idx_name}: {e}")
                        
                    # 2. Run the entry signals scan (0 API calls)
                    run_candle_boundary_scan(now)
                    last_scanned_minute = current_minute_boundary
            
            # C. Print real-time dashboard
            print_dashboard(now)
            
            time.sleep(10)
            
        except KeyboardInterrupt:
            logger.info("Trading interrupted by user. Exiting safely.")
            break
        except Exception as e:
            logger.error(f"Critical error in main loop: {e}")
            time.sleep(10)

if __name__ == '__main__':
    main()
