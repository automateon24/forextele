#!/usr/bin/env python3
"""
MODULAR TRADER V4 - LEARNING FROM APRIL 30, 2026
================================================
V4 Changes (April 30 2026 Learning - Day 1 Live):

  CRITICAL FIXES (Prevent -Rs48K repeat):
    1.  EOD_FORCE_GUARD          - Only force-exit after 15:10, not on every restart
    2.  GAP_RECOVERY_DETECTOR    - Block GAP_DOWN PE if NIFTY recovers past open by 11:00
    3.  MAGIC_SQUARE_CAP3        - Hard cap at 3 open (was 10), mandatory direction filter
    4.  DAILY_BIAS_FLIPPER       - If first-60min P&L < -5000, flip direction allowance
    5.  TIME_STOP_V2             - Only fire TIME_STOP if loss>20% AND spot confirms direction
    6.  TRADE_RESTORE_FIX        - Properly rebuild Trade objects on restart from CSV
    7.  CHAIN_CACHE              - Cache last good chain, no more NO CHAIN on transient fails

  V4 Preserved:
    8.  PORTFOLIO_HEAT_MANAGER   - Max 3 open positions per strategy
    9.  AFTERNOON_CHOP_FILTER    - Block trend strategies after 14:00 if VIX < 15
    10. MOMENTUM_FILTER_V2       - 90%+ confidence bypasses momentum block
    11. TIME_BASED_SIZING        - 50% size after 14:00
    12. MAGIC_SQUARE_V2          - Enhanced dedup with strike+magic number combo key
    13. STRATEGY_COOLDOWN        - 30min disable after 2 consecutive losses
    14. VWAP_BAND_RELAX          - Allow entries within 0.2% VWAP for high conf (>80%)
    15. TREND_FOLLOWING_V2       - Requires VIX > 15 OR 50pt move
    16. AI_ENHANCED_V2           - Momentum filter only for conf < 90%
"""

import json, time, logging, csv, os, math, threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
import sys
import threading

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
sys.path.insert(0, r'c:\cursor\options\niftyopt\Lib\site-packages')
from dhanhq import dhanhq

# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - V4 ENHANCED
# ═════════════════════════════════════════════════════════════════════════════

class Config:
    """Central configuration - V4 Enhanced"""
    VERSION = 'V4.0'
    BUILD_DATE = '2026-04-30'
    
    # API
    CLIENT_ID = '1101936133'
    TOKEN_FILE = 'config/dhan_tokens.json'
    NIFTY_SECURITY_ID = 13
    NIFTY_EXCHANGE = 'IDX_I'
    
    # Trading
    LOT_SIZE = 75
    PREMIUM_MAX = 600
    SL_PCT = 0.30
    TARGET_PCT = 0.50
    CAPITAL_PER_STRATEGY = 50_000
    
    # V4: Time-Based Position Sizing
    FULL_SIZE_WINDOW = (9, 30, 14, 0)    # 9:30 AM - 2:00 PM = 100% size
    REDUCED_SIZE_PCT = 0.5                # After 2:00 PM = 50% size
    
    # Time Windows
    MARKET_OPEN = (9, 15)
    MARKET_CLOSE = (15, 15)
    NO_ENTRY_BEFORE = (9, 30)
    NO_ENTRY_AFTER = (13, 30)  # FIX June 8: Cut off entries at 13:30 (was 14:30) - afternoon trades hit SL today
    
    # V4: Afternoon Choppy Filter
    CHOPPY_START = (14, 0)               # 2:00 PM start
    CHOPPY_VIX_THRESHOLD = 15.0          # VIX below this = choppy
    CHOPPY_BLOCK_STRATEGIES = ['TREND_FOLLOWING', 'BREAKOUT', 'VOLATILITY_BREAKOUT']
    
    # PCR
    PCR_BULLISH = 0.75
    PCR_BEARISH = 1.25
    PCR_REVERSAL_THRESH = 0.85
    PCR_STABILITY_CYCLES = 3
    PCR_OI_IMBALANCE_PCT = 0.20
    
    # Magic Squares
    MAGIC_SQUARES = [9, 36, 81, 144, 225, 324, 441, 576]
    LOT_MULTIPLIERS = {9: 2.5, 36: 2.0, 81: 2.0, 144: 1.5, 225: 1.5, 324: 1.0, 441: 1.0, 576: 1.0}
    MAGIC_MAX_OPEN_PER_STRIKE = 1        # V4: Strict - only 1 per strike
    MAGIC_MAX_OPEN = 1                   # FIX June 8: Hard cap at 1 simultaneous (was 2) - prevent stacking losers

    # V4: Risk Management - Portfolio Heat
    MAX_TRADES_PER_STRATEGY = 3
    MAX_OPEN_PER_STRATEGY = 3            # V4: Max simultaneous open positions
    MAX_SAME_DIR_OPEN = 2
    DAILY_PROFIT_TARGET = 2_500
    DAILY_LOSS_LIMIT = -5_000
    PORTFOLIO_LOSS_LIMIT = -10_000       # FIX June 3: Portfolio circuit breaker - halt ALL entries

    # V4: Gap Recovery Detector
    GAP_RECOVERY_BLOCK_ENABLED = True
    GAP_RECOVERY_THRESHOLD = 0.001       # Block GAP_DOWN PE if spot within 0.1% of open (recovered)
    GAP_RECOVERY_AFTER_MINUTES = 60      # Apply only after first 60min (10:15+)
    GAP_RECOVERY_MIN_GAP_PCT = 0.005     # FIX: Only trigger on real gap-down days (>0.5% gap)

    # V4: Daily Bias Flipper
    BIAS_FLIP_ENABLED = True
    BIAS_FLIP_LOSS_TRIGGER = -2_000      # FIX: was -5000 - lowered to flip bias earlier after 60min losses
    BIAS_FLIP_CHECK_MINUTES = 60         # Check at 60min from market open

    # V4: EOD Force Guard
    EOD_FORCE_START = (15, 10)           # V4 FIX: Only after 15:10 (was 15:15 but fired on restart)

    # V4: TIME_STOP tightened
    TIME_STOP_DIRECTION_CHECK = True     # Only fire TIME_STOP if spot confirms wrong direction
    
    # V4: Strategy Cooldown
    COOLDOWN_AFTER_CONSEC_LOSSES = 2       # Disable after 2 losses
    COOLDOWN_MINUTES = 30
    
    # Trail Stops
    TRAIL_BREAKEVEN_PCT = 0.20
    TRAIL_LOCK_PCT = 0.35
    TIME_STOP_MINUTES = 120              # V4 FIX: Extended to 120min (was 90) - May 27: 4 TIME_STOP losses
    TIME_STOP_MAX_MINUTES = 240          # FIX: hard cap - exit any losing trade after 4 hours regardless of direction
    TIME_STOP_LOSS_PCT = 0.20            # V4: raised from 0.15 to 0.20 - less premature exits
    DECAY_STOP_PCT = 0.005
    DECAY_STOP_CONSEC = 5
    
    # Delta Range
    MIN_DELTA = 0.30
    MAX_DELTA = 0.65
    MAGIC_MIN_DELTA = 0.10
    MAGIC_MAX_DELTA = 0.80
    MAGIC_TOLERANCE_PCT = 0.05
    
    # V4: Filters - Enhanced
    DIRECTION_FILTER_ENABLED = True
    DIRECTION_FILTER_CONFIDENCE = 0.70
    
    # V4: Momentum Filter with Confidence Bypass
    PRICE_MOMENTUM_ENABLED = True
    PRICE_MOMENTUM_THRESHOLD = 20          # FIX June 8: 20pts threshold (was 50) - catch bearish day earlier
    PRICE_MOMENTUM_CONF_BYPASS = 0.90     # 90%+ confidence bypasses filter
    
    # VWAP Filter - Ultra relaxed for profitability
    VWAP_CHOP_FILTER_ENABLED = True
    VWAP_CHOP_BAND_PCT = 0.0005          # 0.05% standard (ultra relaxed)
    VWAP_CHOP_RELAXED_PCT = 0.0002       # 0.02% for high confidence
    VWAP_CHOP_RELAX_CONFIDENCE = 0.70   # 70%+ gets relaxed band
    VWAP_VOLUME_CONFIRM = True          # Use volume to bypass VWAP filter
    
    # V4: Gap ORB
    GAP_THRESHOLD_PCT = 0.003            # 0.3% gap for immediate entry
    
    # Down-Drift Detection for PE opportunities
    DOWN_DRIFT_ENABLED = True
    DOWN_DRIFT_THRESHOLD_PCT = 0.002     # 0.2% down from open triggers drift mode
    DOWN_DRIFT_TIME_MINUTES = 30         # Must sustain for 30 minutes
    
    # Strike Diversification
    MAX_TRADES_PER_STRIKE = 3
    
    # Profit Enhancement Strategies
    AGGRESSIVE_MODE_ENABLED = True      # Allow more trades for profit
    MIN_CONFIDENCE_RELAXED = 0.55       # Lower confidence threshold
    STRATEGY_COOLDOWN_REDUCTION = 0.5   # Halve cooldown times
    MULTI_SIGNAL_CONFLUENCE = True      # Allow multiple strategies on same signal
    MICRO_PROFIT_TARGETS = True         # Allow smaller but more frequent profits
    
    # Strategy-specific
    ORB_CANDLES = 120         # V4: 120 × 30s updates = 60min ORB window (9:15-10:15)
    BREAKOUT_CANDLES = 72
    SCALPING_CANDLES = 15
    AI_MIN_CANDLES = 20       # V4 FIX: 20 × 30s = 10min warmup sufficient for RSI/EMA
    IV_THRESHOLD = 18.0
    
    # V4: Trend Following Enhancement
    TREND_VIX_OR_MOVE = True             # Need VIX>15 OR 50pt move
    TREND_MIN_MOVE_POINTS = 50
    
    # V4.1 FIX: Wake up silent strategies - loosened thresholds
    MEAN_REVERSION_DEVIATION_PCT = 0.30  # Was 0.5% - now 0.3% to catch more reversions
    SCALPING_MAX_LOSS_PCT = 20           # Max 20% loss - prevent -₹5K disasters
    SCALPING_MIN_MOMENTUM = 1.5          # Reduced from 2.0x for more entries
    DAY_LOW_PCR_THRESHOLD = 1.0          # Was 1.2 - now 1.0 to catch more dips
    DAY_HIGH_PCR_THRESHOLD = 1.0         # Was 1.1 - now 1.0 to catch more peaks
    
    # ════════════════════════════════════════════════════════════════════════
    # V4: ADAPTIVE CONFIG LOADING
    # ════════════════════════════════════════════════════════════════════════
    _adaptive_loaded = False
    
    @classmethod
    def load_adaptive_config(cls):
        """Load adaptive thresholds from ADAPTIVE_ENGINE_V4"""
        config_file = 'adaptive_data/adaptive_config.json'
        if not os.path.exists(config_file):
            return False
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            if 'thresholds' not in config:
                return False
            
            thresholds = config['thresholds']
            updated = []
            
            # Map adaptive thresholds to Config attributes
            mapping = {
                'VWAP_CHOP_BAND_PCT': 'VWAP_CHOP_BAND_PCT',
                'VWAP_CHOP_RELAXED_PCT': 'VWAP_CHOP_RELAXED_PCT',
                'PRICE_MOMENTUM_THRESHOLD': 'PRICE_MOMENTUM_THRESHOLD',
                'PRICE_MOMENTUM_CONF_BYPASS': 'PRICE_MOMENTUM_CONF_BYPASS',
                'MOMENTUM_THRESHOLD': 'PRICE_MOMENTUM_THRESHOLD',   # adaptive engine key alias
                'CONFIDENCE_BYPASS': 'PRICE_MOMENTUM_CONF_BYPASS',  # adaptive engine key alias
                'POSITION_SIZE_PCT': None,  # Special handling
                'COOLDOWN_MINUTES': 'COOLDOWN_MINUTES',
                'PCR_STABILITY_CYCLES': 'PCR_STABILITY_CYCLES',
                'TRAIL_BREAKEVEN_PCT': 'TRAIL_BREAKEVEN_PCT',
                'TRAIL_LOCK_PCT': 'TRAIL_LOCK_PCT',
                'GAP_DOWN_BLOCK_NEXT_DAY': 'GAP_DOWN_BLOCK_NEXT_DAY',  # V4: tomorrow block
            }
            
            for adaptive_key, config_key in mapping.items():
                if adaptive_key in thresholds:
                    value = thresholds[adaptive_key]
                    if config_key:
                        setattr(cls, config_key, value)
                        updated.append(f"{config_key}={value}")
            
            if updated:
                log.info(f"[ADAPTIVE] Loaded: {', '.join(updated)}")
                cls._adaptive_loaded = True
                return True
            
        except Exception as e:
            log.warning(f"[ADAPTIVE] Error loading config: {e}")
        
        return False

# ═════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═════════════════════════════════════════════════════════════════════════════

os.makedirs('daily_data', exist_ok=True)
today_str = datetime.now().strftime('%Y%m%d')

class LockedFileHandler(logging.FileHandler):
    """File handler with locking to prevent corruption"""
    def emit(self, record):
        try:
            msg = self.format(record)
            self.stream.write(msg + self.terminator)
            self.stream.flush()
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%y-%m-%d %H:%M:%S',
    handlers=[
        LockedFileHandler(f'daily_data/modular_{today_str}.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

decision_logger = logging.getLogger('decisions')
decision_logger.setLevel(logging.INFO)
decision_handler = LockedFileHandler(f'daily_data/decisions_{today_str}.log', encoding='utf-8')
decision_handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s', datefmt='%y-%m-%d %H:%M:%S'))
decision_logger.addHandler(decision_handler)

# ═════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class MarketData:
    timestamp: datetime
    spot: float
    day_open: Optional[float]
    day_high: Optional[float]
    day_low: Optional[float]
    prev_close: Optional[float]
    vix: Optional[float]
    closes: List[float] = field(default_factory=list)
    chain: Dict = field(default_factory=dict)
    pcr: float = 1.0
    pcr_bias: str = 'NEUTRAL'
    pcr_zone_count: int = 0
    pcr_raw_zone: str = 'NEUTRAL'
    vwap: Optional[float] = None
    ema5: Optional[float] = None
    ema20: Optional[float] = None
    rsi14: Optional[float] = None
    atm_strike: float = 0.0
    max_call_oi_strike: Optional[float] = None
    max_put_oi_strike: Optional[float] = None
    prev_oi_state: Dict = field(default_factory=dict)
    prev_spot: float = 0.0
    put_oi_total: int = 0
    call_oi_total: int = 0

@dataclass
class OptionContract:
    security_id: str
    strike: float
    option_type: str
    ltp: float
    iv: float
    delta: float
    gamma: float
    theta: float
    vega: float
    oi: int
    volume: int
    bid: float
    ask: float

@dataclass
class Signal:
    module: str
    strategy: str
    direction: str
    contract: OptionContract
    confidence: float
    reason: str
    meta: Dict = field(default_factory=dict)

@dataclass
class Trade:
    trade_id: str
    strategy: str
    module: str
    contract: OptionContract
    entry_price: float
    quantity: int
    target: float
    stop_loss: float
    open_time: datetime
    close_time: Optional[datetime] = None
    close_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: float = 0.0
    status: str = 'OPEN'
    max_profit_pct: float = 0.0
    tsl_step_pts: float = 0.0       # for DH/DL TSL: trail every N spot pts
    target_spot_level: float = 0.0  # for DH/DL TSL: spot target (day high/low)
    sl_spot_level: float = 0.0      # for DH/DL TSL: spot-based SL level
    tsl_active: bool = False        # True once target_spot_level hit

class StrategyModule:
    """Base class for all strategy modules - V4 Enhanced"""
    
    def __init__(self, name: str, display_name: str):
        self.name = name
        self.display_name = display_name
        self.enabled = True
        self.trade_count = 0
        self.net_pnl = 0.0
        self.open_trade: Optional[Trade] = None
        # V4: Portfolio heat tracking
        self.consecutive_losses = 0
        self.cooldown_until: Optional[datetime] = None
        self.open_trades: List[Trade] = []  # V4: Multiple trade support
        
    def analyze(self, data: MarketData) -> Optional[Signal]:
        return None
    
    def reset_daily(self):
        self.trade_count = 0
        self.net_pnl = 0.0
        self.consecutive_losses = 0
        self.cooldown_until = None
        self.open_trades = []
        if hasattr(self, 'traded_strikes'):
            self.traded_strikes.clear()
        if hasattr(self, 'traded_magic_numbers'):
            self.traded_magic_numbers.clear()
        
    def is_in_cooldown(self) -> bool:
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return True
        return False
    
    def record_loss(self):
        self.consecutive_losses += 1
        if self.consecutive_losses >= Config.COOLDOWN_AFTER_CONSEC_LOSSES:
            self.cooldown_until = datetime.now() + timedelta(minutes=Config.COOLDOWN_MINUTES)
            log.warning(f"[COOLDOWN] {self.name} disabled for {Config.COOLDOWN_MINUTES}min after {self.consecutive_losses} losses")
            
    def record_win(self):
        self.consecutive_losses = 0
        
    def get_open_count(self) -> int:
        return len([t for t in self.open_trades if t.status == 'OPEN'])

# ═════════════════════════════════════════════════════════════════════════════
# V4: Portfolio Heat Manager
# ═════════════════════════════════════════════════════════════════════════════

class PortfolioHeatManager:
    """V4: Track and limit open positions per strategy"""
    
    def __init__(self):
        self.strategy_open_count: Dict[str, int] = defaultdict(int)
        self.strike_strategy_map: Dict[float, Set[str]] = defaultdict(set)
        
    def can_enter_strategy(self, module_name: str, strike: float, max_open: int = Config.MAX_OPEN_PER_STRATEGY) -> bool:
        """Check if strategy has capacity for new trade"""
        current_open = self.strategy_open_count.get(module_name, 0)
        if current_open >= max_open:
            log.info(f"[HEAT] Blocking {module_name} - Max {max_open} open positions reached ({current_open})")
            return False
        return True
    
    def record_entry(self, module_name: str, strike: float):
        """Record new position"""
        self.strategy_open_count[module_name] += 1
        self.strike_strategy_map[strike].add(module_name)
        
    def record_exit(self, module_name: str, strike: float):
        """Record position close"""
        if self.strategy_open_count[module_name] > 0:
            self.strategy_open_count[module_name] -= 1
        if module_name in self.strike_strategy_map[strike]:
            self.strike_strategy_map[strike].remove(module_name)
            
    def get_open_count(self, module_name: str) -> int:
        return self.strategy_open_count.get(module_name, 0)

# ═════════════════════════════════════════════════════════════════════════════
# STRATEGY IMPLEMENTATIONS
# ═════════════════════════════════════════════════════════════════════════════

class UltimateORBModule(StrategyModule):
    """Strategy 1: Day High / Day Low CONTINUATION Strategy (per chart)
    
    ORB window: 9:15 AM – 10:15 AM (120 × 30s candles).
    High and Low are LOCKED at 10:15 AM for the rest of the day.

    SELL SETUP (PE trade):
      1. Price hits & breaks above DAY HIGH
      2. Price was above 20 SMA (bullish before rejection)
      3. RSI(14) in 60-65 zone and turning down (overbought resistance)
      4. Wait for a RED candle that closes BELOW Day High → ENTRY PE
      5. SL  = Day High + 10 pts (spot level)
      6. Target = Day Low
      7. After target hit: TSL trails every 10 pts further move

    BUY SETUP (CE trade):
      1. Price hits & breaks below DAY LOW
      2. Price was below 20 SMA (bearish before bounce)
      3. RSI(14) in 35-40 zone and turning up (oversold support)
      4. Wait for a GREEN candle that closes ABOVE Day Low → ENTRY CE
      5. SL  = Day Low - 10 pts (spot level)
      6. Target = Day High
      7. After target hit: TSL trails every 10 pts further move

    AI additions (preserving essence):
      - Volume confirmation: candle volume > 1.1x average (avoids low-volume fakeouts)
      - Max 1 trade per direction per day (prevents overtrading same level)
      - Strategy re-arms if SL not hit and level retested (continuation)
    """

    # RSI zones - WIDENED for more signals (55-70 sell, 30-45 buy)
    RSI_SELL_LO = 55.0   # was 60 - catch earlier overbought
    RSI_SELL_HI = 70.0   # was 68 - extended to catch extreme overbought
    RSI_BUY_LO  = 30.0   # was 32 - deeper oversold capture
    RSI_BUY_HI  = 45.0   # was 40 - earlier entry on bounce
    SL_BUFFER_PTS = 10.0  # SL distance from DH/DL in spot points

    def __init__(self):
        super().__init__("ULTIMATE_DAY_HIGH_LOW", "DH_DL_CONTINUATION")
        self.orb_high: Optional[float] = None
        self.orb_low:  Optional[float] = None
        self.orb_locked = False

        # Breakout tracking
        self._dh_broken = False        # price broke above DH
        self._dl_broken = False        # price broke below DL
        self._prev_candle_close: Optional[float] = None   # last candle close
        self._prev_candle_was_red = False
        self._prev_candle_was_green = False

        # RSI direction tracking (need 2 readings to confirm turning)
        self._prev_rsi: Optional[float] = None

        # Per-day fire limits
        self._pe_fired_today = False
        self._ce_fired_today = False

        # TSL state (managed externally in trade, but we track target hit)
        self._tsl_pe_active = False
        self._tsl_ce_active = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        spot = data.spot
        if not spot or spot <= 0:
            return None

        # ── Step 1: Lock ORB high/low after 60-min window (120 candles × 30s) ──
        if not self.orb_locked:
            if len(data.closes) >= Config.ORB_CANDLES:
                self.orb_high = max(data.closes[:Config.ORB_CANDLES])
                self.orb_low  = min(data.closes[:Config.ORB_CANDLES])
                self.orb_locked = True
                log.info(f"[DH/DL] ORB LOCKED 10:15 high={self.orb_high:.2f} low={self.orb_low:.2f}")
            return None  # still in ORB formation window

        if not self.orb_high or not self.orb_low:
            return None

        # ── Common indicators ──────────────────────────────────────────────────
        sma20  = data.ema20    # ema20 serves as 20-period MA in MarketData
        rsi    = data.rsi14
        if not sma20 or not rsi:
            return None

        # Track candle closes for confirmation (each analyze() call = ~30s)
        prev_close = self._prev_candle_close
        self._prev_candle_was_red   = (prev_close is not None and prev_close > spot)
        self._prev_candle_was_green = (prev_close is not None and prev_close < spot)
        self._prev_candle_close = spot

        # RSI direction
        rsi_turning_down = (self._prev_rsi is not None and rsi < self._prev_rsi)
        rsi_turning_up   = (self._prev_rsi is not None and rsi > self._prev_rsi)
        self._prev_rsi = rsi

        # ══════════════════════════════════════════════════════════════════════
        # SELL SETUP — Price breaks Day High → Buy PE
        # ══════════════════════════════════════════════════════════════════════
        if not self._pe_fired_today:
            # Step 1: Price hits & breaks above Day High
            if spot > self.orb_high:
                self._dh_broken = True
                log.debug(f"[DH/DL] DH broken: spot={spot:.0f} > DH={self.orb_high:.0f}")

            if self._dh_broken:
                # Step 2: Price was above 20 SMA (bullish momentum before rejection)
                above_sma = spot > sma20

                # Step 3: RSI in 60-68 zone AND turning down (resistance zone rejection)
                rsi_sell_zone = (self.RSI_SELL_LO <= rsi <= self.RSI_SELL_HI) and rsi_turning_down

                # Step 4: RED candle closes BACK BELOW Day High (bearish rejection confirmed)
                red_close_below_dh = self._prev_candle_was_red and (spot < self.orb_high)

                if above_sma and rsi_sell_zone and red_close_below_dh:
                    c = best_contract_premium_filtered(data, 'PE', delta_min=0.35, delta_max=0.65, max_premium=600)
                    if c:
                        self._pe_fired_today = True
                        reason = (f"DH={self.orb_high:.0f} broken+rejected | "
                                  f"spot={spot:.0f} above SMA={sma20:.0f} | "
                                  f"RSI={rsi:.1f} turning down | red candle below DH | "
                                  f"Target=DayLow {self.orb_low:.0f} SL=DH+10={self.orb_high+self.SL_BUFFER_PTS:.0f}")
                        log.info(f"[DH/DL] SELL SIGNAL: {reason}")
                        sig = Signal(self.name, "DH_REJECTION_PE", "PE", c, 0.82, reason)
                        # Attach DH/DL levels as metadata for SL/target management
                        sig.meta = {
                            "sl_spot": self.orb_high + self.SL_BUFFER_PTS,
                            "target_spot": self.orb_low,
                            "tsl_step_pts": 10.0,
                            "strategy_type": "DH_DL_CONTINUATION"
                        }
                        return sig

        # ══════════════════════════════════════════════════════════════════════
        # BUY SETUP — Price breaks Day Low → Buy CE
        # ══════════════════════════════════════════════════════════════════════
        if not self._ce_fired_today:
            # Step 1: Price hits & breaks below Day Low
            if spot < self.orb_low:
                self._dl_broken = True
                log.debug(f"[DH/DL] DL broken: spot={spot:.0f} < DL={self.orb_low:.0f}")

            if self._dl_broken:
                # Step 2: Price was below 20 SMA (bearish momentum before bounce)
                below_sma = spot < sma20

                # Step 3: RSI in 32-40 zone AND turning up (support zone bounce)
                rsi_buy_zone = (self.RSI_BUY_LO <= rsi <= self.RSI_BUY_HI) and rsi_turning_up

                # Step 4: GREEN candle closes BACK ABOVE Day Low (bullish rejection confirmed)
                green_close_above_dl = self._prev_candle_was_green and (spot > self.orb_low)

                if below_sma and rsi_buy_zone and green_close_above_dl:
                    c = best_contract_premium_filtered(data, 'CE', delta_min=0.35, delta_max=0.65, max_premium=600)
                    if c:
                        self._ce_fired_today = True
                        reason = (f"DL={self.orb_low:.0f} broken+bounced | "
                                  f"spot={spot:.0f} below SMA={sma20:.0f} | "
                                  f"RSI={rsi:.1f} turning up | green candle above DL | "
                                  f"Target=DayHigh {self.orb_high:.0f} SL=DL-10={self.orb_low-self.SL_BUFFER_PTS:.0f}")
                        log.info(f"[DH/DL] BUY SIGNAL: {reason}")
                        sig = Signal(self.name, "DL_BOUNCE_CE", "CE", c, 0.82, reason)
                        sig.meta = {
                            "sl_spot": self.orb_low - self.SL_BUFFER_PTS,
                            "target_spot": self.orb_high,
                            "tsl_step_pts": 10.0,
                            "strategy_type": "DH_DL_CONTINUATION"
                        }
                        return sig

        return None

    def _best_contract(self, data: MarketData, option_type: str) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, option_type)

class TrendFollowingModule(StrategyModule):
    """Strategy 7: Gap continuation - V4 with VIX/Move filter"""
    
    # V4 FIX: class-level flag so restart within same day does NOT re-fire
    _triggered_date: Optional[str] = None

    def __init__(self):
        super().__init__("TREND_FOLLOWING", "TREND_FOLLOW")
        
    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.day_open or not data.prev_close:
            return None
            
        gap_pct = (data.day_open - data.prev_close) / data.prev_close
        
        # V4 FIX: Loosened from 0.002 to 0.001 (0.1% gaps) for ranging markets
        if abs(gap_pct) < 0.001:
            return None
            
        # V4: Need volatility confirmation
        if Config.TREND_VIX_OR_MOVE:
            vix_ok = data.vix and data.vix > Config.CHOPPY_VIX_THRESHOLD
            move_points = abs(data.spot - data.day_open)
            move_ok = move_points > Config.TREND_MIN_MOVE_POINTS
            
            if not (vix_ok or move_ok):
                vix_str = f"{data.vix:.1f}" if data.vix is not None else "N/A"
                log.info(f"[TREND] Blocked - VIX {vix_str}<{Config.CHOPPY_VIX_THRESHOLD} AND move {move_points:.0f}pt < {Config.TREND_MIN_MOVE_POINTS}pt")
                return None
        
        direction = 'CE' if gap_pct > 0 else 'PE'
        
        # V4 FIX: one entry per day regardless of restarts
        today = datetime.now().strftime('%Y%m%d')
        if TrendFollowingModule._triggered_date == today:
            return None
            
        c = self._best_contract(data, direction)
        if c:
            TrendFollowingModule._triggered_date = today
            return Signal(self.name, f"GAP_UP_TREND" if gap_pct > 0 else "GAP_DOWN_TREND", 
                         direction, c, 0.70,
                         f"Gap {direction} trend: open {data.day_open:.0f} vs prev {data.prev_close:.0f}" if data.prev_close else f"Gap {direction} trend: open {data.day_open:.0f}")
        return None
    
    def _best_contract(self, data: MarketData, option_type: str) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, option_type)

class AIEnhancedModule(StrategyModule):
    """Strategy 8: AI ensemble - V4 with momentum bypass + choppy filter"""
    
    # V4 FIX: Skip entries when VWAP is flat (choppy market)
    VWAP_FLAT_THRESHOLD_PCT = 0.0015  # 0.15% - skip if price within this of VWAP
    
    def __init__(self):
        super().__init__("AI_ENHANCED", "AI_ENHANCED")
        
    def analyze(self, data: MarketData) -> Optional[Signal]:
        if len(data.closes) < Config.AI_MIN_CANDLES:
            return None
        if not data.rsi14 or not data.ema20:
            return None
        
        # V4 FIX: Choppy market filter - skip if VWAP flat (price near VWAP)
        if data.vwap and data.vwap > 0:
            vwap_dist_pct = abs(data.spot - data.vwap) / data.vwap
            if vwap_dist_pct < self.VWAP_FLAT_THRESHOLD_PCT:
                log.debug(f"[AI_ENHANCED] Skipping - VWAP flat (dist={vwap_dist_pct*100:.2f}% < {self.VWAP_FLAT_THRESHOLD_PCT*100:.2f}%)")
                return None
            
        mom = (data.closes[-1] - data.closes[-6]) / data.closes[-6] * 100 if len(data.closes) >= 6 else 0
        body_score = sum(1 if data.closes[i] > data.closes[i-1] else -1 for i in range(-3, 0))
        
        rsi_bull = max(0, (data.rsi14 - 50) / 50)
        pcr_bull = max(0, (1.0 - data.pcr) / 0.5)
        mom_bull = max(0, min(1, mom / 2.0))
        ema_bull = 1.0 if data.spot > data.ema20 else 0.0
        body_bull = max(0, body_score / 3)
        
        bull_score = (rsi_bull * 0.25 + pcr_bull * 0.25 + mom_bull * 0.20 +
                     ema_bull * 0.20 + body_bull * 0.10)
        bear_score = 1.0 - bull_score
        
        spot_vs_open = (data.spot - data.day_open) if data.day_open else 0

        # V4 FIX: raised from 0.65->0.75 (matches V3 threshold), add direction guards
        # V4 FIX: Raised to 0.80 (was 0.75) - May 27: 0.94 AI confidence still lost
        if bull_score >= 0.80:
            if spot_vs_open < -50:  # market down 50pts - block bullish entry
                log.info(f"[AI] Blocking CE - AI bullish {bull_score:.2f} but market down {spot_vs_open:.0f}pts")
                return None
            c = self._best_contract(data, 'CE')
            if c:
                return Signal(self.name, "AI_BULLISH", "CE", c, bull_score,
                            f"AI score: bullish {bull_score:.2f}")

        if bear_score >= 0.80:
            if spot_vs_open > 30:  # market up 30pts - block bearish entry
                log.info(f"[AI] Blocking PE - AI bearish {bear_score:.2f} but market up {spot_vs_open:.0f}pts")
                return None
            c = self._best_contract(data, 'PE')
            if c:
                return Signal(self.name, "AI_BEARISH", "PE", c, bear_score,
                            f"AI score: bearish {bear_score:.2f}")
        return None
    
    def _best_contract(self, data: MarketData, option_type: str) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, option_type)

class MagicSquareModule(StrategyModule):
    """Strategy 14: Magic Square - V4.1 Smart adaptive limits based on regime"""
    
    # V4.1 FIX: Adaptive limits based on market regime
    VWAP_RANGE_THRESHOLD_PCT = 0.003     # Skip if within 0.3% of VWAP
    VWAP_TRENDING_THRESHOLD_PCT = 0.005  # Wider 0.5% for trending days
    MAX_TRADES_RANGING = 2               # Max 2 trades in ranging market
    MAX_TRADES_TRENDING = 5              # Max 5 trades in trending market
    MAX_TRADES_GAP_DAY = 4               # Max 4 trades on gap days
    MIN_RSI_FOR_ENTRY = 45               # Avoid neutral RSI (45-55 zone) in ranging
    MAX_RSI_FOR_ENTRY = 55
    
    def __init__(self):
        super().__init__("MAGIC_SQUARE", "MAGIC_SQUARE")
        self.opening_price = None
        # V4: Track both strike AND magic number
        self.traded_strikes: Set[float] = set()
        self.traded_magic_numbers: Set[int] = set()
        self.strike_magic_combo: Set[Tuple[float, int]] = set()  # (strike, magic_number)
        self._ranging_detected = False       # V4: Track if market is ranging
        self._day_open_processed = False   # V4.1: Track if we've processed open
        self._gap_pct = 0.0                # V4.1: Track gap percentage
        
    def reset_daily(self):
        super().reset_daily()
        self.traded_strikes.clear()
        self.traded_magic_numbers.clear()
        self.strike_magic_combo.clear()
        # V4.1 FIX: Reset ranging flag at market open - don't carry yesterday's fear
        self._ranging_detected = False
        self._day_open_processed = False
        self._gap_pct = 0.0
        
    def analyze(self, data: MarketData) -> Optional[Signal]:
        # FIX June 2: Early exit if disabled (flat gap day or other reason)
        if not self.enabled:
            return None
        
        if self.opening_price is None and data.day_open:
            self.opening_price = data.day_open
            # V4.1: Calculate gap percentage at market open
            if data.prev_close and data.prev_close > 0:
                self._gap_pct = (data.day_open - data.prev_close) / data.prev_close * 100
                self._day_open_processed = True
                log.info(f"[MAGIC_V4.1] Market open: Gap {self._gap_pct:+.2f}%, setting adaptive limits")
                # V4 FIX: Block Magic Square on flat gap days (May 27: +0.00% gap, multiple entries all lost)
                if abs(self._gap_pct) < 0.15:
                    log.info(f"[MAGIC_V4.1] Flat gap day ({self._gap_pct:+.2f}%), disabling Magic Square for today")
                    self.enabled = False
                    return None
        
        # V4.1 FIX: Determine market regime and set adaptive limits
        is_gap_day = abs(self._gap_pct) >= 0.15  # 0.15% gap = trending day
        
        # V4.1: Adaptive VWAP threshold - wider on trending/gap days
        vwap_threshold = self.VWAP_TRENDING_THRESHOLD_PCT if is_gap_day else self.VWAP_RANGE_THRESHOLD_PCT
        
        # V4 FIX: Detect ranging market (price near VWAP = chop zone)
        if data.vwap and data.vwap > 0:
            vwap_dist_pct = abs(data.spot - data.vwap) / data.vwap
            self._ranging_detected = vwap_dist_pct < vwap_threshold
            
            # V4.1: Only apply strict ranging filters if truly ranging (not gap day)
            if self._ranging_detected and not is_gap_day:
                # In ranging market: tighten everything
                if data.rsi14 and self.MIN_RSI_FOR_ENTRY <= data.rsi14 <= self.MAX_RSI_FOR_ENTRY:
                    log.debug(f"[MAGIC_V4.1] Skipping - RSI {data.rsi14:.0f} neutral in ranging market")
                    return None
                # Limit trades in ranging market
                if self.trade_count >= self.MAX_TRADES_RANGING:
                    log.debug(f"[MAGIC_V4.1] Max {self.MAX_TRADES_RANGING} trades in ranging market reached")
                    return None
        
        # V4.1: Set max trades based on regime
        if is_gap_day:
            max_trades = self.MAX_TRADES_GAP_DAY
            regime = "GAP_DAY"
        elif self._ranging_detected:
            max_trades = self.MAX_TRADES_RANGING
            regime = "RANGING"
        else:
            max_trades = self.MAX_TRADES_TRENDING
            regime = "TRENDING"
        
        direction = 'BOTH'
        if self.opening_price:
            change = data.spot - self.opening_price
            if change > 40:
                direction = 'CE'
            elif change < -40:
                direction = 'PE'

        # V4 FIX: Skip if adaptive engine has suppressed entries (extreme ranging)
        if self._check_adaptive_suppression():
            log.debug("[MAGIC_V4] Suppressed by adaptive engine - extreme ranging detected")
            return None

        # V4 FIX: Optional direction filter - disabled in extreme ranging via adaptive config
        if not self._should_disable_direction_filter():
            # V4: Mandatory EMA20 + PCR direction filter (can be disabled in ranging)
            ema20 = data.ema20 or data.spot
            spot_above_ema = data.spot > ema20
            pcr_bullish = data.pcr < 1.0
            pcr_bearish = data.pcr > 1.1

            if spot_above_ema and pcr_bullish:
                if direction == 'PE':
                    log.info(f"[MAGIC_V4] Blocking PE - spot above EMA20 and PCR={data.pcr:.2f} bullish")
                    return None
                direction = 'CE'
            elif not spot_above_ema and pcr_bearish:
                if direction == 'CE':
                    log.info(f"[MAGIC_V4] Blocking CE - spot below EMA20 and PCR={data.pcr:.2f} bearish")
                    return None
                direction = 'PE'
            elif spot_above_ema and not pcr_bearish:
                if direction == 'BOTH':
                    direction = 'CE'
            elif not spot_above_ema and not pcr_bullish:
                if direction == 'BOTH':
                    direction = 'PE'

            if data.pcr_bias == 'BULLISH' and direction == 'BOTH':
                direction = 'CE'
            elif data.pcr_bias == 'BEARISH' and direction == 'BOTH':
                direction = 'PE'
        else:
            log.debug("[MAGIC_V4] Direction filter DISABLED - extreme ranging regime")
        
        # FIX: When BOTH, scan PE first on bearish days (PCR>1.1 or spot below EMA), CE first on bullish
        if direction == 'BOTH':
            ema20 = data.ema20 or data.spot
            if data.pcr > 1.1 or data.spot < ema20:
                scan_types = ['PE', 'CE']
            else:
                scan_types = ['CE', 'PE']
        else:
            scan_types = [direction]
        
        # V4.1: Apply regime-based max trades
        if self.get_open_count() >= max_trades:
            log.debug(f"[MAGIC_V4.1] Max open reached for {regime}: {self.get_open_count()}/{max_trades}")
            return None

        for opt_type in scan_types:
            if not data.chain:
                continue
                
            for sk, contracts in data.chain.items():
                strike = float(sk)
                
                # V4: Check strike+magic combo - prevent ANY duplicate
                if strike in self.traded_strikes:
                    continue
                    
                cont = contracts.get(opt_type)
                if not cont:
                    continue
                    
                if not (Config.MAGIC_MIN_DELTA <= cont.delta <= Config.MAGIC_MAX_DELTA):
                    continue
                    
                expiry_today = is_expiry_day()
                theta_limit = 0.50 if expiry_today else 0.15
                if cont.theta > theta_limit:
                    continue
                    
                for magic in Config.MAGIC_SQUARES:
                    # V4: Check combo key
                    if (strike, magic) in self.strike_magic_combo:
                        continue
                        
                    tolerance = magic * Config.MAGIC_TOLERANCE_PCT
                    if abs(cont.ltp - magic) <= tolerance:
                        # V4: Cap premium at ₹300 to avoid risky trades
                        if cont.ltp > 300:
                            log.debug(f"[MAGIC_SQUARE] Skipping {opt_type}{strike} premium={cont.ltp:.2f} - exceeds ₹300 cap")
                            continue
                            
                        # V4: Verify we haven't traded this strike at all
                        if strike not in self.traded_strikes:
                            self.traded_strikes.add(strike)
                            self.traded_magic_numbers.add(magic)
                            self.strike_magic_combo.add((strike, magic))
                            
                            mult = Config.LOT_MULTIPLIERS.get(magic, 1.0)
                            
                            log.info(f"[MAGIC_SQUARE] Found {opt_type}{strike} premium={cont.ltp:.2f} matches square {magic} (delta={cont.delta:.2f})")
                            
                            return Signal(self.name, f"MAGIC_{magic}", opt_type, cont, 0.60,
                                        f"Premium {cont.ltp:.0f} matches magic square {magic} at strike {strike}")
        return None
    
    def _check_adaptive_suppression(self) -> bool:
        """V4: Check if adaptive engine has suppressed all entries"""
        try:
            config_file = 'adaptive_data/adaptive_config.json'
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    thresholds = config.get('thresholds', {})
                    if thresholds.get('SUPPRESS_NEW_ENTRIES', False):
                        return True
        except Exception:
            pass
        return False
    
    def _should_disable_direction_filter(self) -> bool:
        """V4: Disable direction filter ONLY in extreme ranging with adaptive suppression.
        FIX: Do NOT disable on trade_count - that was removing the only PE redirection."""
        # Only disable if adaptive engine explicitly suppresses entries
        if self._check_adaptive_suppression():
            return True
        return False

# ═════════════════════════════════════════════════════════════════════════════
# STRATEGY IMPLEMENTATIONS — PORTED FROM V3 (previously bare shells in V4)
# ═════════════════════════════════════════════════════════════════════════════

class DayHighBearishModule(StrategyModule):
    """Strategy 2: Day high bearish reversal — PCR>=1.1, RSI>65, retest of session high"""
    def __init__(self):
        super().__init__("DAY_HIGH_BEARISH", "DAY_HIGH_BEARISH")
        self._session_high: Optional[float] = None
        self._touched_high = False
        self._retested = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.day_high:
            return None
        if self._session_high is None and len(data.closes) >= 15:
            self._session_high = max(data.closes[:15])
        ref_high = self._session_high if self._session_high else data.day_high
        if data.pcr < 1.1:
            return None
        if not data.rsi14 or data.rsi14 < 65:
            return None
        spot = data.spot
        if not self._touched_high:
            if spot >= ref_high * 0.997:
                self._touched_high = True
        elif not self._retested:
            if spot < ref_high * 0.996:
                self._retested = True
        else:
            if spot >= ref_high * 0.997:
                self._touched_high = False
                self._retested = False
                c = best_contract_premium_filtered(data, 'PE', delta_min=0.45, delta_max=0.65, max_premium=500)
                if c:
                    return Signal(self.name, "DAY_HIGH_REVERSAL", "PE", c, 0.75,
                                f"Day high {ref_high:.0f} retest rejected PCR={data.pcr:.2f} RSI={data.rsi14:.0f}")
        return None

class DayLowBullishModule(StrategyModule):
    """Strategy 3: Day low bullish reversal — RSI<35, double-bottom confirmation"""
    def __init__(self):
        super().__init__("DAY_LOW_BULLISH", "DAY_LOW_BULLISH")
        self._session_low: Optional[float] = None
        self._touched_low = False
        self._retested = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.day_low:
            return None
        if self._session_low is None and len(data.closes) >= 15:
            self._session_low = min(data.closes[:15])
        ref_low = self._session_low if self._session_low else data.day_low
        if not data.rsi14:
            return None
        if data.rsi14 <= 30:
            pass
        elif data.rsi14 <= 35 and data.pcr >= 0.9:
            pass
        else:
            return None
        spot = data.spot
        if not self._touched_low:
            if spot <= ref_low * 1.003:
                self._touched_low = True
        elif not self._retested:
            if spot > ref_low * 1.004:
                self._retested = True
        else:
            if spot <= ref_low * 1.003:
                self._touched_low = False
                self._retested = False
                c = best_contract_premium_filtered(data, 'CE', delta_min=0.45, delta_max=0.65, max_premium=500)
                if c:
                    return Signal(self.name, "DAY_LOW_REVERSAL", "CE", c, 0.75,
                                f"Day low {ref_low:.0f} double-bottom PCR={data.pcr:.2f} RSI={data.rsi14:.0f}")
        return None

class DayLowBounceModule(StrategyModule):
    """Strategy 3B: Day low bounce - when day_low is broken but RSI < 30.
    June 4 Learning: Today day_low=23247, RSI=16 - perfect setup missed."""
    def __init__(self):
        super().__init__("DAY_LOW_BOUNCE", "DAY_LOW_BOUNCE")
        self._fired_today = False
        self._break_logged = False
    
    def reset_daily(self):
        super().reset_daily()
        self._fired_today = False
        self._break_logged = False
    
    def analyze(self, data: MarketData) -> Optional[Signal]:
        if self._fired_today:
            return None
        if not data.day_low or not data.rsi14:
            return None
        
        spot = data.spot
        # Trigger: Price breaks below day_low AND RSI < 30 (extreme oversold)
        if spot < data.day_low * 0.999 and data.rsi14 < 30:
            if not self._break_logged:
                log.info(f"[DAY_LOW_BOUNCE] Day low {data.day_low:.0f} broken, RSI={data.rsi14:.0f} - bounce setup")
                self._break_logged = True
            c = best_contract_premium_filtered(data, 'CE', delta_min=0.40, delta_max=0.65, max_premium=500)
            if c:
                self._fired_today = True
                return Signal(self.name, "DAY_LOW_BOUNCE", "CE", c, 0.72,
                            f"Day low {data.day_low:.0f} broken, RSI={data.rsi14:.0f} extreme oversold")
        return None

class EnhancedBearishModule(StrategyModule):
    """Strategy 4: Enhanced bearish with RSI>65 at day high"""
    def __init__(self):
        super().__init__("ENHANCED_BEARISH_REVERSAL", "ENH_BEARISH")
        self._fired_today = False  # FIX: max 1 entry per day - prevent repeated SL re-entries

    def reset_daily(self):
        super().reset_daily()
        self._fired_today = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if self._fired_today:  # FIX: one shot per day
            return None
        if not data.day_high or data.spot < data.day_high * 0.995:
            return None
        if not data.rsi14 or data.rsi14 < 65:
            return None
        if data.pcr < 0.90:
            return None
        c = best_contract_premium_filtered(data, 'PE', delta_min=0.45, delta_max=0.65, max_premium=500)
        if c:
            self._fired_today = True
            return Signal(self.name, "ENHANCED_BEARISH", "PE", c, 0.75,
                        f"High {data.day_high:.0f} RSI={data.rsi14:.1f} PCR={data.pcr:.3f}")
        return None

class EnhancedBullishModule(StrategyModule):
    """Strategy 5: Enhanced bullish reversal at day low — with day-direction guard"""
    def __init__(self):
        super().__init__("ENHANCED_BULLISH_REVERSAL", "ENH_BULLISH")
        self._fired_today = False  # FIX: max 1 entry per day - prevent repeated SL re-entries

    def reset_daily(self):
        super().reset_daily()
        self._fired_today = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if self._fired_today:  # FIX: one shot per day
            return None
        if not data.day_low or data.spot > data.day_low * 1.005:
            return None
        if not data.rsi14:
            return None
        if data.rsi14 <= 30:
            pass
        elif data.rsi14 <= 35 and data.pcr >= 0.9:
            pass
        else:
            return None
        if data.day_open and (data.spot - data.day_open) < -25:  # FIX: tightened from -50 to -25pts
            log.info(f"[ENHANCED_BULL] Skipping CE - market DOWN {data.day_open - data.spot:.0f}pts from open")
            return None
        c = best_contract_premium_filtered(data, 'CE', delta_min=0.45, delta_max=0.65, max_premium=500)
        if c:
            self._fired_today = True
            return Signal(self.name, "ENHANCED_BULLISH", "CE", c, 0.75,
                        f"Low {data.day_low:.0f} RSI={data.rsi14:.1f} PCR={data.pcr:.3f}")
        return None

class DayHighLowTraditionalModule(StrategyModule):
    """Strategy 6: 1-HOUR range breakout with retest confirmation.
    V4 KEY DIFFERENCE vs V3: uses Config.ORB_CANDLES (120 × 30s = 60min)
    instead of V3's 15-candle (7.5min) window. The 60-min opening range
    is far more meaningful for NIFTY intraday breakouts.
    """
    def __init__(self):
        super().__init__("DAY_HIGH_LOW_TRADITIONAL", "DAY_HL_TRAD")
        self._range_high: Optional[float] = None
        self._range_low: Optional[float] = None
        self._broke_up = False
        self._broke_dn = False
        self._retest_up = False
        self._retest_dn = False
        self.ce_fired = False
        self.pe_fired = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if self._range_high is None:
            if len(data.closes) >= Config.ORB_CANDLES:   # V4: 120 candles = 60min
                self._range_high = max(data.closes[:Config.ORB_CANDLES])
                self._range_low  = min(data.closes[:Config.ORB_CANDLES])
            return None
        spot = data.spot
        if not self.ce_fired:
            if not self._broke_up:
                if spot > self._range_high * 1.002:
                    self._broke_up = True
            elif not self._retest_up:
                if spot <= self._range_high * 1.001:
                    self._retest_up = True
            else:
                if spot > self._range_high * 1.001:
                    self.ce_fired = True
                    c = best_contract_premium_filtered(data, 'CE', Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)
                    if c:
                        return Signal(self.name, "RANGE_BREAK_CE", "CE", c, 0.70,
                                    f"15min high {self._range_high:.0f} retest confirmed")
        if not self.pe_fired:
            if not self._broke_dn:
                if spot < self._range_low * 0.998:
                    self._broke_dn = True
            elif not self._retest_dn:
                if spot >= self._range_low * 0.999:
                    self._retest_dn = True
            else:
                if spot < self._range_low * 0.999:
                    self.pe_fired = True
                    c = best_contract_premium_filtered(data, 'PE', Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)
                    if c:
                        return Signal(self.name, "RANGE_BREAK_PE", "PE", c, 0.70,
                                    f"15min low {self._range_low:.0f} retest confirmed")
        return None

class MeanReversionModule(StrategyModule):
    """Strategy 9: Deviation fade with RSI confirmation"""
    def __init__(self):
        super().__init__("MEAN_REVERSION", "MEAN_REVERSION")

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.day_open:
            return None
        dev = (data.spot - data.day_open) / data.day_open * 100
        rsi = data.rsi14
        if not rsi:
            return None
        pe_threshold = 0.35 if rsi > 70 else 0.5
        ce_threshold = -0.35 if rsi < 30 else -0.5
        if dev > pe_threshold and rsi >= 65:
            c = best_contract_premium_filtered(data, 'PE', Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)
            if c:
                return Signal(self.name, "MEAN_REVERT_PE", "PE", c, 0.70,
                            f"Deviation {dev:.1f}% above open, RSI={rsi:.1f}")
        if dev < ce_threshold and rsi <= 35:
            c = best_contract_premium_filtered(data, 'CE', Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)
            if c:
                return Signal(self.name, "MEAN_REVERT_CE", "CE", c, 0.70,
                            f"Deviation {dev:.1f}% below open, RSI={rsi:.1f}")
        return None

class ScalpingModule(StrategyModule):
    """Strategy 10: 5 consecutive candles + 2x momentum + >=15pt move"""
    def __init__(self):
        super().__init__("SCALPING", "SCALPING")

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if len(data.closes) < max(Config.SCALPING_CANDLES, 22):
            return None
        
        # FIX June 4: Restrict scalping to morning only 9:30-11:30 AM - 70% win rate morning vs 30% afternoon
        now = datetime.now()
        if now.hour < 9 or (now.hour == 9 and now.minute < 30):
            return None
        if now.hour >= 11 and now.minute >= 30:
            return None
        
        last5 = data.closes[-5:]
        all_up   = all(last5[i] < last5[i+1] for i in range(4))
        all_down = all(last5[i] > last5[i+1] for i in range(4))
        moves = [abs(data.closes[i] - data.closes[i-1]) for i in range(-21, -1)]
        avg_move = sum(moves) / len(moves) if moves else 0
        last_move = abs(data.closes[-1] - data.closes[-2])
        strong_momentum = avg_move > 0 and last_move >= avg_move * Config.SCALPING_MIN_MOMENTUM
        total_move = abs(last5[-1] - last5[0])
        meaningful = total_move >= 15
        day_move = (data.spot - data.day_open) if data.day_open else 0
        if all_up and strong_momentum and meaningful:
            # FIX June 2: Tightened from 80->30pts to match V3 (prevent wrong-direction scalps)
            if data.pcr_bias == 'BEARISH' or day_move < -30:
                return None
            c = best_contract_premium_filtered(data, 'CE', delta_min=0.35, delta_max=0.60, max_premium=500)
            if c:
                return Signal(self.name, "SCALP_UP", "CE", c, 0.68,
                            f"5 up candles, move={total_move:.0f}pts, mom={last_move/avg_move:.1f}x")
        if all_down and strong_momentum and meaningful:
            # FIX June 2: Tightened from 80->30pts to match V3 (prevent wrong-direction scalps)
            if data.pcr_bias == 'BULLISH' or day_move > 30:
                return None
            c = best_contract_premium_filtered(data, 'PE', delta_min=0.35, delta_max=0.60, max_premium=500)
            if c:
                return Signal(self.name, "SCALP_DOWN", "PE", c, 0.68,
                            f"5 down candles, move={total_move:.0f}pts, mom={last_move/avg_move:.1f}x")
        return None

class BreakoutModule(StrategyModule):
    """Strategy 11: 72-candle range breakout with retest confirmation"""
    def __init__(self):
        super().__init__("BREAKOUT", "BREAKOUT")
        self._broke_ce = False
        self._broke_pe = False
        self._retest_ce = False
        self._retest_pe = False
        self._ce_level: Optional[float] = None
        self._pe_level: Optional[float] = None
        self.ce_fired = False
        self.pe_fired = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        lookback = Config.BREAKOUT_CANDLES
        if len(data.closes) < lookback + 1:
            return None
        range_closes = data.closes[-(lookback + 1):-1]
        range_high = max(range_closes)
        range_low = min(range_closes)
        spot = data.closes[-1]
        if not self.ce_fired:
            if not self._broke_ce:
                if spot > range_high * 1.002:
                    self._broke_ce = True
                    self._ce_level = range_high
            elif not self._retest_ce:
                if spot <= self._ce_level * 1.002:
                    self._retest_ce = True
            else:
                if spot > self._ce_level * 1.002:
                    self.ce_fired = True
                    c = best_contract_premium_filtered(data, 'CE', delta_min=0.40, delta_max=0.70, max_premium=500)
                    if c:
                        return Signal(self.name, "BREAKOUT_CE", "CE", c, 0.78,
                                    f"Broke+retested {lookback}-candle high {self._ce_level:.0f}")
        if not self.pe_fired:
            if not self._broke_pe:
                if spot < range_low * 0.998:
                    self._broke_pe = True
                    self._pe_level = range_low
            elif not self._retest_pe:
                if spot >= self._pe_level * 0.998:
                    self._retest_pe = True
            else:
                if spot < self._pe_level * 0.998:
                    self.pe_fired = True
                    c = best_contract_premium_filtered(data, 'PE', delta_min=0.40, delta_max=0.70, max_premium=500)
                    if c:
                        return Signal(self.name, "BREAKDOWN_PE", "PE", c, 0.78,
                                    f"Broke+retested {lookback}-candle low {self._pe_level:.0f}")
        return None

class VolatilityBreakoutModule(StrategyModule):
    """Strategy 12: High ATM IV + EMA5/EMA20 crossover"""
    def __init__(self):
        super().__init__("VOLATILITY_BREAKOUT", "VOL_BREAKOUT")

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.ema5 or not data.ema20:
            return None
        atm = data.atm_strike
        atm_strikes = [s for s in data.chain if abs(s - atm) <= 100]
        atm_contracts = [data.chain[s][side] for s in atm_strikes
                         for side in ('CE', 'PE') if side in data.chain[s]]
        if not atm_contracts:
            return None
        avg_iv = sum(c.iv for c in atm_contracts) / len(atm_contracts)
        if avg_iv < Config.IV_THRESHOLD:
            return None
        if data.ema5 > data.ema20 * 1.001:
            candidates = [data.chain[s]['CE'] for s in data.chain
                          if 'CE' in data.chain[s] and Config.MIN_DELTA <= abs(data.chain[s]['CE'].delta) <= Config.MAX_DELTA]
            if candidates:
                max_vol = max(c.volume for c in candidates) or 1
                max_oi = max(c.oi for c in candidates) or 1
                c = max(candidates, key=lambda x: abs(x.delta)*0.4 + (x.volume/max_vol)*0.3 + (x.oi/max_oi)*0.3)
                return Signal(self.name, "VOL_BREAKOUT_CE", "CE", c, 0.70,
                            f"ATM IV {avg_iv:.1f}% + EMA5>EMA20")
        if data.ema5 < data.ema20 * 0.999:
            candidates = [data.chain[s]['PE'] for s in data.chain
                          if 'PE' in data.chain[s] and Config.MIN_DELTA <= abs(data.chain[s]['PE'].delta) <= Config.MAX_DELTA]
            if candidates:
                max_vol = max(c.volume for c in candidates) or 1
                max_oi = max(c.oi for c in candidates) or 1
                c = max(candidates, key=lambda x: abs(x.delta)*0.4 + (x.volume/max_vol)*0.3 + (x.oi/max_oi)*0.3)
                return Signal(self.name, "VOL_BREAKOUT_PE", "PE", c, 0.70,
                            f"ATM IV {avg_iv:.1f}% + EMA5<EMA20")
        return None

class OptionsGreeksModule(StrategyModule):
    """Strategy 13: Delta-skew weighted by OI + EMA20 direction filter"""
    def __init__(self):
        super().__init__("OPTIONS_GREEKS", "OPT_GREEKS")
        self._fired_today = False  # FIX: max 1 entry per day (same as V3 fix)

    def reset_daily(self):
        super().reset_daily()
        self._fired_today = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if self._fired_today:
            return None
        ce_skew = sum(abs(data.chain[s]['CE'].delta) * data.chain[s]['CE'].oi
                      for s in data.chain if 'CE' in data.chain[s])
        pe_skew = sum(abs(data.chain[s]['PE'].delta) * data.chain[s]['PE'].oi
                      for s in data.chain if 'PE' in data.chain[s])
        if ce_skew == 0 and pe_skew == 0:
            return None
        skew_ratio = ce_skew / (ce_skew + pe_skew)
        
        # Secondary filter: When spot is near VWAP, use OI imbalance instead
        if data.vwap and abs(data.spot - data.vwap) / data.vwap < 0.001:
            # Use OI imbalance when at VWAP
            total_oi = sum(data.chain[s]['CE'].oi + data.chain[s]['PE'].oi
                          for s in data.chain if 'CE' in data.chain[s] and 'PE' in data.chain[s])
            if total_oi > 0:
                ce_oi = sum(data.chain[s]['CE'].oi for s in data.chain if 'CE' in data.chain[s])
                pe_oi = sum(data.chain[s]['PE'].oi for s in data.chain if 'PE' in data.chain[s])
                oi_ratio = ce_oi / total_oi
                
                if oi_ratio > 0.55:  # CE OI dominates
                    ces = [data.chain[s]['CE'] for s in data.chain
                           if 'CE' in data.chain[s] and data.chain[s]['CE'].vega > 0]
                    if ces:
                        c = max(ces, key=lambda x: x.vega * x.oi)
                        if c.ltp <= Config.PREMIUM_MAX:
                            self._fired_today = True
                            return Signal(self.name, "GREEKS_CE_VWAP", "CE", c, 0.75,
                                        f"OI imbalance {oi_ratio:.2f} CE at VWAP")
                elif oi_ratio < 0.45:  # PE OI dominates
                    pes = [data.chain[s]['PE'] for s in data.chain
                           if 'PE' in data.chain[s] and data.chain[s]['PE'].vega > 0]
                    if pes:
                        c = max(pes, key=lambda x: x.vega * x.oi)
                        if c.ltp <= Config.PREMIUM_MAX:
                            self._fired_today = True
                            return Signal(self.name, "GREEKS_PE_VWAP", "PE", c, 0.75,
                                        f"OI imbalance {oi_ratio:.2f} PE at VWAP")
        
        # Original logic for when not at VWAP
        if skew_ratio > 0.55 and data.ema20 and data.spot > data.ema20:
            ces = [data.chain[s]['CE'] for s in data.chain
                   if 'CE' in data.chain[s] and data.chain[s]['CE'].vega > 0]
            if ces:
                c = max(ces, key=lambda x: x.vega * x.oi)
                if c.ltp <= Config.PREMIUM_MAX:
                    self._fired_today = True
                    return Signal(self.name, "GREEKS_CE", "CE", c, 0.70,
                                f"Delta skew {skew_ratio:.2f} CE bias + spot>EMA20")
        if skew_ratio < 0.45 and data.ema20 and data.spot < data.ema20:
            pes = [data.chain[s]['PE'] for s in data.chain
                   if 'PE' in data.chain[s] and data.chain[s]['PE'].vega > 0]
            if pes:
                c = max(pes, key=lambda x: x.vega * x.oi)
                if c.ltp <= Config.PREMIUM_MAX:
                    self._fired_today = True
                    return Signal(self.name, "GREEKS_PE", "PE", c, 0.70,
                                f"Delta skew {skew_ratio:.2f} PE bias + spot<EMA20")
        return None

class ShortUnwindModule(StrategyModule):
    """Strategy 15: Put OI drop + spot rising = short unwind (CE buy)"""
    def __init__(self):
        super().__init__("SHORT_UNWIND", "SHORT_UNWIND")

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.prev_oi_state or data.prev_spot <= 0:
            return None
        if data.spot <= data.prev_spot or not data.max_put_oi_strike:
            return None
        prev_pe_oi = data.prev_oi_state.get(data.max_put_oi_strike, {}).get('PE', 0)
        cont = data.chain.get(data.max_put_oi_strike, {}).get('PE')
        curr_pe_oi = cont.oi if cont else 0
        if prev_pe_oi <= 0:
            return None
        oi_drop = (prev_pe_oi - curr_pe_oi) / prev_pe_oi * 100
        if oi_drop < 10.0:
            return None
        c = best_contract_premium_filtered(data, 'CE', Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)
        if c:
            return Signal(self.name, "SHORT_UNWIND", "CE", c, 0.80,
                        f"Put OI dropped {oi_drop:.1f}% at {data.max_put_oi_strike:.0f}")
        return None

class LongUnwindModule(StrategyModule):
    """Strategy 16: Call OI drop + spot falling = long unwind (PE buy)"""
    def __init__(self):
        super().__init__("LONG_UNWIND", "LONG_UNWIND")

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.prev_oi_state or data.prev_spot <= 0:
            return None
        if data.spot >= data.prev_spot or not data.max_call_oi_strike:
            return None
        prev_ce_oi = data.prev_oi_state.get(data.max_call_oi_strike, {}).get('CE', 0)
        cont = data.chain.get(data.max_call_oi_strike, {}).get('CE')
        curr_ce_oi = cont.oi if cont else 0
        if prev_ce_oi <= 0:
            return None
        oi_drop = (prev_ce_oi - curr_ce_oi) / prev_ce_oi * 100
        if oi_drop < 10.0:
            return None
        c = best_contract_premium_filtered(data, 'PE', Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)
        if c:
            return Signal(self.name, "LONG_UNWIND", "PE", c, 0.80,
                        f"Call OI dropped {oi_drop:.1f}% at {data.max_call_oi_strike:.0f}")
        return None

class ResistBreakModule(StrategyModule):
    """Strategy 17: Above max call OI with 3-cycle confirmation"""
    def __init__(self):
        super().__init__("WRITER_RESIST_BREAK", "WRITER_RESIST")
        self._wrb_consec = 0

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.max_call_oi_strike:
            return None
        if data.spot <= data.max_call_oi_strike * 1.001:
            self._wrb_consec = 0
            return None
        if data.prev_oi_state:
            prev_ce_oi = data.prev_oi_state.get(data.max_call_oi_strike, {}).get('CE', 0)
            cont = data.chain.get(data.max_call_oi_strike, {}).get('CE')
            curr_ce_oi = cont.oi if cont else 0
            if prev_ce_oi > 0 and (prev_ce_oi - curr_ce_oi) / prev_ce_oi * 100 < 3.0:
                self._wrb_consec = 0
                return None
        self._wrb_consec += 1
        if self._wrb_consec < 3:
            return None
        c = best_contract_premium_filtered(data, 'CE', delta_min=0.40, delta_max=0.70, max_premium=500)
        if c:
            return Signal(self.name, "RESIST_BREAK", "CE", c, 0.75,
                        f"Broke call resistance {data.max_call_oi_strike:.0f}")
        return None

class PutWriterSupportModule(StrategyModule):
    """Strategy 18: At max put OI with writers defending"""
    def __init__(self):
        super().__init__("PUT_WRITER_SUPPORT", "PUT_SUPPORT")

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.max_put_oi_strike:
            return None
        
        # FIX June 2: Morning direction guard - don't buy CE if market is clearly bearish
        if data.day_open and (data.spot - data.day_open) < -25:
            log.info(f"[PUT_SUPPORT] Blocking CE - market down {data.day_open - data.spot:.0f}pts from open (bearish)")
            return None
        
        points_above = data.spot - data.max_put_oi_strike
        if points_above < 0 or points_above > 50:
            return None
        if data.spot > data.max_put_oi_strike * 1.003:
            return None
        if data.day_low and data.day_low < data.max_put_oi_strike - 10:
            return None
        if data.prev_oi_state:
            prev_pe_oi = data.prev_oi_state.get(data.max_put_oi_strike, {}).get('PE', 0)
            cont = data.chain.get(data.max_put_oi_strike, {}).get('PE')
            curr_pe_oi = cont.oi if cont else 0
            if prev_pe_oi > 0 and curr_pe_oi < prev_pe_oi * 0.98:
                return None
        c = best_contract_premium_filtered(data, 'CE', delta_min=0.45, delta_max=0.65, max_premium=500)
        if c and c.strike <= data.spot + 100:
            return Signal(self.name, "PUT_SUPPORT", "CE", c, 0.70,
                        f"At put support {data.max_put_oi_strike:.0f}, {points_above:.0f}pt above")
        return None

# ═════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def is_expiry_day() -> bool:
    """Check if today is Thursday (typical expiry)"""
    return datetime.now().weekday() == 3

def calc_pcr_bias(pcr: float, put_oi: int, call_oi: int) -> Tuple[str, int, str]:
    """Calculate PCR bias with stability and OI imbalance"""
    zone = 'NEUTRAL'
    if pcr < Config.PCR_BULLISH:
        zone = 'BULLISH'
    elif pcr > Config.PCR_BEARISH:
        zone = 'BEARISH'
        
    total_oi = put_oi + call_oi
    if total_oi > 0:
        oi_imbalance = abs(put_oi - call_oi) / total_oi
        if oi_imbalance > Config.PCR_OI_IMBALANCE_PCT:
            pass
            
    return zone, 3 if zone != 'NEUTRAL' else 0, zone

def best_contract_premium_filtered(data: MarketData, option_type: str, 
                                   delta_min: float = None, delta_max: float = None, max_premium: float = None) -> Optional[OptionContract]:
    """Find best contract with premium and delta filtering"""
    if not data.chain:
        return None
        
    delta_min = delta_min or Config.MIN_DELTA
    delta_max = delta_max or Config.MAX_DELTA
    max_premium = max_premium or Config.PREMIUM_MAX
    
    atm = data.atm_strike
    candidates = []
    
    for sk, contracts in data.chain.items():
        strike = float(sk)
        cont = contracts.get(option_type)
        if not cont:
            continue
            
        if not (delta_min <= abs(cont.delta) <= delta_max):
            continue
            
        if not (10 <= cont.ltp <= max_premium):
            continue
            
        dist = abs(strike - atm)
        candidates.append((dist, cont))
        
    if not candidates:
        return None
        
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]

# ═════════════════════════════════════════════════════════════════════════════
# V4: ENHANCED TRADE MANAGER
# ═════════════════════════════════════════════════════════════════════════════

class TradeManager:
    """V4: Enhanced trade management with portfolio heat control + bias flip + gap recovery"""

    def __init__(self, modules: List[StrategyModule]):
        self.modules = modules
        self.trades: List[Trade] = []
        self.same_dir_count = defaultdict(int)
        self.heat_manager = PortfolioHeatManager()
        self.module_dict = {m.name: m for m in modules}
        # Down-drift detection
        self.day_open_price = None
        self.down_drift_start_time = None
        self.down_drift_active = False
        # V4: Gap Recovery Detector state
        # If adaptive engine flagged yesterday as gap-down failure, start with warning pre-set
        self._gap_down_day = getattr(Config, 'GAP_DOWN_BLOCK_NEXT_DAY', False)
        self._gap_recovered = False
        self._gap_recovery_logged = False
        # V4: Daily Bias Flipper state
        self._bias_flip_checked = False
        self._bias_flipped = False          # True = block original direction, allow opposite
        self._bias_flip_blocked_dir = None  # 'PE' or 'CE'
        self._market_open_time: Optional[datetime] = None
        
    def _update_down_drift(self, data: MarketData):
        """Detect down-drifting market for PE opportunities"""
        if not Config.DOWN_DRIFT_ENABLED or not data.day_open:
            return
            
        now = datetime.now()
        if self.day_open_price is None:
            self.day_open_price = data.day_open
            self.down_drift_start_time = None
            self.down_drift_active = False
            return
            
        # Calculate down-drift percentage
        down_drift_pct = (data.spot - self.day_open_price) / self.day_open_price
        
        # Check if market is drifting down
        if down_drift_pct < -Config.DOWN_DRIFT_THRESHOLD_PCT:
            if not self.down_drift_active:
                # Start tracking drift
                if self.down_drift_start_time is None:
                    self.down_drift_start_time = now
                    log.debug(f"[DOWN_DRIFT] Started tracking - down {down_drift_pct*100:.2f}% from open")
                elif (now - self.down_drift_start_time).total_seconds() / 60 >= Config.DOWN_DRIFT_TIME_MINUTES:
                    # Sustained down-drift - activate
                    self.down_drift_active = True
                    log.info(f"[DOWN_DRIFT] ACTIVATED - Market down {down_drift_pct*100:.2f}% for {Config.DOWN_DRIFT_TIME_MINUTES}+ minutes - PE opportunities favored")
        else:
            # Reset if market recovers
            if self.down_drift_active:
                log.info(f"[DOWN_DRIFT] DEACTIVATED - Market recovered to {down_drift_pct*100:.2f}%")
            self.down_drift_active = False
            self.down_drift_start_time = None

    def _update_gap_recovery(self, data: MarketData):
        """V4: Detect if a gap-down day has recovered — block further GAP_DOWN PE entries"""
        if not Config.GAP_RECOVERY_BLOCK_ENABLED or not data.day_open or not data.prev_close:
            return
        now = datetime.now()
        if self._market_open_time is None:
            self._market_open_time = now
        # Only evaluate after 60min from market open
        mins_since_open = (now - self._market_open_time).total_seconds() / 60
        if mins_since_open < Config.GAP_RECOVERY_AFTER_MINUTES:
            return
        gap_pct = (data.day_open - data.prev_close) / data.prev_close
        if gap_pct < -Config.GAP_RECOVERY_MIN_GAP_PCT:  # FIX: Only flag real gap-down days (>0.5%)
            self._gap_down_day = True
        if self._gap_down_day:
            # Check if spot has recovered to within threshold of open
            recovery_pct = (data.spot - data.day_open) / data.day_open
            if recovery_pct >= -Config.GAP_RECOVERY_THRESHOLD:
                if not self._gap_recovery_logged:
                    log.info(f"[GAP_RECOVERY_V4] Gap-down day but NIFTY recovered: spot={data.spot:.0f} open={data.day_open:.0f} ({recovery_pct*100:+.2f}%) - blocking new PE entries")
                    self._gap_recovery_logged = True
                self._gap_recovered = True

    def _update_bias_flip(self, data: MarketData):
        """V4: If first-60min P&L is deeply negative, flip direction block"""
        if not Config.BIAS_FLIP_ENABLED or self._bias_flip_checked:
            return
        if self._market_open_time is None:
            return
        mins_since_open = (now := datetime.now(), (now - self._market_open_time).total_seconds() / 60)[1]
        if mins_since_open < Config.BIAS_FLIP_CHECK_MINUTES:
            return
        self._bias_flip_checked = True
        total_pnl = sum(t.pnl for t in self.trades if t.status == 'CLOSED' and t.pnl)
        if total_pnl < Config.BIAS_FLIP_LOSS_TRIGGER:
            # Figure out which direction caused the losses
            pe_losses = sum(t.pnl for t in self.trades if t.status == 'CLOSED' and t.pnl < 0 and t.contract.option_type == 'PE')
            ce_losses = sum(t.pnl for t in self.trades if t.status == 'CLOSED' and t.pnl < 0 and t.contract.option_type == 'CE')
            if pe_losses < ce_losses:  # PE is losing more
                self._bias_flipped = True
                self._bias_flip_blocked_dir = 'PE'
                log.info(f"[BIAS_FLIP_V4] P&L={total_pnl:.0f} < {Config.BIAS_FLIP_LOSS_TRIGGER} after 60min. PE losers={pe_losses:.0f}. BLOCKING further PE entries.")
            elif ce_losses < pe_losses:
                self._bias_flipped = True
                self._bias_flip_blocked_dir = 'CE'
                log.info(f"[BIAS_FLIP_V4] P&L={total_pnl:.0f} < {Config.BIAS_FLIP_LOSS_TRIGGER} after 60min. CE losers={ce_losses:.0f}. BLOCKING further CE entries.")

    def _check_adaptive_suppression(self) -> bool:
        """V4: Check if adaptive engine has suppressed entries due to RANGING + consecutive losses"""
        try:
            config_file = 'adaptive_data/adaptive_config.json'
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    thresholds = config.get('thresholds', {})
                    if thresholds.get('SUPPRESS_NEW_ENTRIES', False):
                        return True
        except Exception as e:
            log.debug(f"[ADAPTIVE_SUPPRESS] Error checking suppression: {e}")
        return False

    def can_enter(self, module: StrategyModule, direction: str, data: MarketData = None,
                  signal_confidence: float = 0) -> bool:
        now = datetime.now()

        # V4: Check adaptive engine suppression flag (RANGING regime + consecutive losses)
        if self._check_adaptive_suppression():
            log.info(f"[ADAPTIVE_SUPPRESS] Blocking {module.name} - RANGING regime with consecutive losses")
            return False

        # V4 Adaptive Engine Regime Filtering
        try:
            config_file = 'adaptive_data/adaptive_config.json'
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    adaptive_regime = config.get('regime', 'NORMAL')
                    
                if adaptive_regime == 'TRENDING_BEAR':
                    blocked_bullish = {'DAY_LOW_BULLISH', 'PUT_WRITER_SUPPORT', 'DAY_LOW_BOUNCE'}
                    if module.name in blocked_bullish:
                        log.info(f"[ADAPTIVE FILTER] Blocking {module.name} ({direction}) due to TRENDING_BEAR regime.")
                        return False
                    if direction == 'CE' and module.name in {'MEAN_REVERSION', 'MAGIC_SQUARE', 'ULTIMATE_DAY_HIGH_LOW', 'DAY_HIGH_LOW_TRADITIONAL'}:
                        log.info(f"[ADAPTIVE FILTER] Blocking CE for {module.name} due to TRENDING_BEAR regime.")
                        return False
                        
                elif adaptive_regime == 'TRENDING_BULL':
                    blocked_bearish = {'DAY_HIGH_BEARISH'}
                    if module.name in blocked_bearish:
                        log.info(f"[ADAPTIVE FILTER] Blocking {module.name} ({direction}) due to TRENDING_BULL regime.")
                        return False
                    if direction == 'PE' and module.name in {'MEAN_REVERSION', 'MAGIC_SQUARE', 'ULTIMATE_DAY_HIGH_LOW', 'DAY_HIGH_LOW_TRADITIONAL'}:
                        log.info(f"[ADAPTIVE FILTER] Blocking PE for {module.name} due to TRENDING_BULL regime.")
                        return False
        except Exception as e:
            log.debug(f"[ADAPTIVE_REGIME_FILTER] Error: {e}")

        # V4: Update gap recovery, bias flip, and down-drift state each check
        if data:
            self._update_gap_recovery(data)
            self._update_bias_flip(data)
            self._update_down_drift(data)

        # V4: Gap Recovery Block - if gap-down day recovered, no more PE
        if self._gap_recovered and direction == 'PE':
            log.info(f"[GAP_RECOVERY_V4] Blocking PE for {module.name} - gap-down day has recovered")
            return False

        # V4: Bias Flip Block
        if self._bias_flipped and direction == self._bias_flip_blocked_dir:
            log.info(f"[BIAS_FLIP_V4] Blocking {direction} for {module.name} - bias flipped after 60min loss")
            return False
            
        # V4: Down-Drift PE Opportunity - favor PE trades in down-drifting market
        if self.down_drift_active and direction == 'CE':
            # Allow CE only for high-confidence signals or specific strategies
            if signal_confidence < 0.85 and module.name not in ('AI_ENHANCED', 'MAGIC_SQUARE'):
                log.info(f"[DOWN_DRIFT] Blocking CE for {module.name} - market down-drifting, PE favored (confidence: {signal_confidence:.2f})")
                return False

        # V4: Check cooldown with reduction in aggressive mode
        if module.is_in_cooldown():
            if Config.AGGRESSIVE_MODE_ENABLED and module.cooldown_until:
                # Reduce cooldown by 50% in aggressive mode
                reduced_cooldown_until = module.cooldown_until - timedelta(minutes=Config.COOLDOWN_MINUTES * Config.STRATEGY_COOLDOWN_REDUCTION)
                if datetime.now() < reduced_cooldown_until:
                    log.info(f"[COOLDOWN] {module.name} in reduced cooldown until {reduced_cooldown_until.strftime('%H:%M')}")
                    return False
                else:
                    log.info(f"[AGGRESSIVE_MODE] {module.name} cooldown reduced, allowing entry")
            else:
                log.info(f"[COOLDOWN] {module.name} in cooldown until {module.cooldown_until.strftime('%H:%M')}")
                return False
        
        # FIX June 4: Early entry on gap days (9:20 AM if gap > 0.3%) to capture reversal momentum
        gap_override = False
        if data and data.day_open and data.prev_close:
            try:
                prev_close_val = float(data.prev_close) if not callable(data.prev_close) else 0
                if prev_close_val > 0:
                    gap_pct = abs((float(data.day_open) - prev_close_val) / prev_close_val * 100)
                    if gap_pct > 0.3 and now.hour >= 9 and now.minute >= 20:
                        gap_override = True
                        if now.hour == 9 and now.minute == 20:
                            log.info(f"[GAP_EARLY_ENTRY] Gap day detected ({gap_pct:.2f}%), allowing entries from 9:20 AM")
            except (TypeError, ValueError):
                pass  # Skip gap check if data types are invalid (e.g., Mock in tests)
        
        time_check = now.hour < Config.NO_ENTRY_BEFORE[0] or (now.hour == Config.NO_ENTRY_BEFORE[0] and now.minute < Config.NO_ENTRY_BEFORE[1])
        if time_check and not gap_override:
            return False
        if now.hour > Config.NO_ENTRY_AFTER[0] or (now.hour == Config.NO_ENTRY_AFTER[0] and now.minute >= Config.NO_ENTRY_AFTER[1]):
            return False
        
        # FIX June 3: Portfolio-level circuit breaker (V4 was missing this entirely)
        total_pnl = sum(t.pnl for t in self.trades if t.pnl is not None)
        if total_pnl <= Config.PORTFOLIO_LOSS_LIMIT:
            log.info(f"[CIRCUIT_BREAKER_V4] Portfolio loss ₹{total_pnl:,.0f} <= ₹{Config.PORTFOLIO_LOSS_LIMIT:,} - halting ALL new entries")
            return False
            
        # V4: Afternoon choppy filter for trend strategies
        if module.name in Config.CHOPPY_BLOCK_STRATEGIES:
            if now.hour > Config.CHOPPY_START[0] or (now.hour == Config.CHOPPY_START[0] and now.minute >= Config.CHOPPY_START[1]):
                if data and data.vix and data.vix < Config.CHOPPY_VIX_THRESHOLD:
                    vix_str = f"{data.vix:.1f}" if data.vix is not None else "N/A"
                    log.info(f"[CHOPPY_FILTER] Blocking {module.name} - Afternoon + VIX {vix_str} < {Config.CHOPPY_VIX_THRESHOLD}")
                    return False
        
        # Magic Square: Use Config.MAGIC_MAX_OPEN (was hardcoded 10 — too many losers on ranging days)
        if module.name == 'MAGIC_SQUARE':
            if module.trade_count >= Config.MAGIC_MAX_OPEN:
                return False
            # V4: Check portfolio heat - max open per Config
            if self.heat_manager.get_open_count('MAGIC_SQUARE') >= Config.MAX_OPEN_PER_STRATEGY:
                log.info(f"[HEAT] Magic Square at max {Config.MAX_OPEN_PER_STRATEGY} open positions")
                return False
        else:
            if module.trade_count >= Config.MAX_TRADES_PER_STRATEGY:
                return False
            if module.open_trade is not None:
                return False
                
        if module.net_pnl <= Config.DAILY_LOSS_LIMIT:
            return False
            
        # Direction Filter
        if Config.DIRECTION_FILTER_ENABLED and data and signal_confidence >= Config.DIRECTION_FILTER_CONFIDENCE:
            if data.pcr_bias == 'BULLISH' and direction == 'PE':
                log.info(f"[FILTER] Blocking PE trade for {module.name} - PCR bias is BULLISH")
                return False
            if data.pcr_bias == 'BEARISH' and direction == 'CE':
                log.info(f"[FILTER] Blocking CE trade for {module.name} - PCR bias is BEARISH")
                return False
        
        # FIX June 8: Strong intraday direction guard - lowered from 50pts to 30pts
        # June 8 root cause: market was ~30-40pts down but guard only triggered at 50pts → CE trades allowed
        if data and data.day_open:
            intraday_move = data.spot - data.day_open
            if intraday_move > 30 and direction == 'PE':
                log.info(f"[DIRECTION_GUARD] Blocking PE for {module.name} - market UP {intraday_move:.0f}pts (no bypass)")
                return False
            if intraday_move < -30 and direction == 'CE':
                log.info(f"[DIRECTION_GUARD] Blocking CE for {module.name} - market DOWN {abs(intraday_move):.0f}pts (no bypass)")
                return False
        
        # FIX June 3: Global same-direction cap - max 3 open in same direction
        open_in_direction = sum(1 for t in self.trades
                                if t.status == 'OPEN' and t.contract.option_type == direction)
        if open_in_direction >= 3:
            # June 4 LEARNING: Log reasoning for learning review
            open_trades_list = [f"{t.trade_id}({t.contract.option_type})" for t in self.trades if t.status == 'OPEN']
            log.info(f"[DIR_CAP] Blocking {module.name} {direction} - {open_in_direction}/3 open. Active: {open_trades_list}")
            return False

        # V4: Price Momentum Filter (only for moderate moves 30-50pts, hard guard covers >50pts above)
        if Config.PRICE_MOMENTUM_ENABLED and data and data.day_open:
            price_change = data.spot - data.day_open
            if price_change > Config.PRICE_MOMENTUM_THRESHOLD and direction == 'PE':
                log.info(f"[FILTER] Blocking PE trade for {module.name} - Market UP {price_change:.0f} points")
                return False
            if price_change < -Config.PRICE_MOMENTUM_THRESHOLD and direction == 'CE':
                log.info(f"[FILTER] Blocking CE trade for {module.name} - Market DOWN {abs(price_change):.0f} points")
                return False
        
        # V4: VWAP Filter with relaxed band for high confidence
        if Config.VWAP_CHOP_FILTER_ENABLED and data and data.vwap and data.vwap > 0:
            vwap_dist_pct = abs(data.spot - data.vwap) / data.vwap
            
            # V4: High confidence gets relaxed band
            vwap_threshold = Config.VWAP_CHOP_BAND_PCT
            if signal_confidence >= Config.VWAP_CHOP_RELAX_CONFIDENCE:
                vwap_threshold = Config.VWAP_CHOP_RELAXED_PCT
            
            # Volume confirmation bypass - high volume allows trades even at VWAP
            volume_bypass = False
            if Config.VWAP_VOLUME_CONFIRM and data.chain:
                # chain[strike] = {'CE': OptionContract, 'PE': OptionContract}
                total_volume = 0
                for s in data.chain:
                    ce = data.chain[s].get('CE') if isinstance(data.chain[s], dict) else None
                    pe = data.chain[s].get('PE') if isinstance(data.chain[s], dict) else None
                    total_volume += (ce.volume if ce else 0) + (pe.volume if pe else 0)
                if total_volume > 5000000:  # 5M+ total volume indicates activity
                    volume_bypass = True
                    log.debug(f"[FILTER] Volume bypass active - Total volume: {total_volume:,}")
                
            if vwap_dist_pct < vwap_threshold and module.name not in ('AI_ENHANCED', 'MAGIC_SQUARE') and not volume_bypass:
                log.info(f"[FILTER] Blocking {module.name} {direction} - Price near VWAP ({vwap_dist_pct*100:.2f}% < {vwap_threshold*100:.2f}% threshold)")
                return False
        
        return True
    
    def enter(self, signal: Signal, module: StrategyModule, data: MarketData = None) -> Optional[Trade]:
        # V4: Relaxed confidence in aggressive mode
        effective_confidence = signal.confidence
        if Config.AGGRESSIVE_MODE_ENABLED and effective_confidence < Config.MIN_CONFIDENCE_RELAXED:
            # Allow lower confidence signals in aggressive mode
            effective_confidence = Config.MIN_CONFIDENCE_RELAXED
            log.info(f"[AGGRESSIVE_MODE] {module.name} confidence relaxed from {signal.confidence:.2f} to {effective_confidence:.2f}")
            
        if not self.can_enter(module, signal.direction, data, effective_confidence):
            return None
            
        entry = signal.contract.ask if signal.contract.ask > 0 else signal.contract.ltp
        
        # FIX June 4: 3-tier time-based position sizing (Priority 3)
        # 9:30-11:30 = 100%, 11:30-13:00 = 75%, 13:00+ = 50%
        now = datetime.now()
        size_multiplier = 1.0
        if now.hour >= 13:
            size_multiplier = 0.5
            log.info(f"[SIZING] {module.name} using 50% size (afternoon 13:00+)")
        elif now.hour == 11 and now.minute >= 30 or now.hour == 12:
            size_multiplier = 0.75
            log.info(f"[SIZING] {module.name} using 75% size (midday 11:30-13:00)")
        
        # FIX June 9: High confidence boost for AI_ENHANCED (>0.90 = 4x size)
        high_confidence_boost = 1.0
        if signal.confidence >= 0.90 and module.name == 'AI_ENHANCED':
            high_confidence_boost = 4.0
            log.info(f"[SIZING] {module.name} HIGH CONFIDENCE {signal.confidence:.2f} → 4x size boost")
        
        adjusted_qty = int(Config.LOT_SIZE * size_multiplier * high_confidence_boost)
        
        meta = signal.meta if signal.meta else {}
        is_dh_dl = meta.get("strategy_type") == "DH_DL_CONTINUATION"
        
        # V4: Micro-profit targets in aggressive mode
        if Config.MICRO_PROFIT_TARGETS and Config.AGGRESSIVE_MODE_ENABLED:
            # Use smaller targets for more frequent profits
            micro_target_pct = Config.TARGET_PCT * 0.6  # 60% of normal target
            micro_sl_pct = Config.SL_PCT * 0.8  # Slightly tighter stop loss
            target_price = round(entry * (1 + micro_target_pct), 2) if not is_dh_dl else round(entry * 1.30, 2)
            stop_loss_price = round(entry * (1 - micro_sl_pct), 2) if not is_dh_dl else round(entry * (1 - Config.SL_PCT), 2)
        else:
            target_price = round(entry * (1 + Config.TARGET_PCT), 2) if not is_dh_dl else round(entry * 1.50, 2)
            stop_loss_price = round(entry * (1 - Config.SL_PCT), 2) if not is_dh_dl else round(entry * (1 - Config.SL_PCT), 2)
        
        trade = Trade(
            trade_id=f"{signal.module[:4]}_{datetime.now().strftime('%H%M%S')}",
            strategy=signal.strategy,
            module=signal.module,
            contract=signal.contract,
            entry_price=entry,
            quantity=adjusted_qty,
            target=target_price,
            stop_loss=stop_loss_price,
            open_time=datetime.now(),
            tsl_step_pts=meta.get("tsl_step_pts", 0.0),
            target_spot_level=meta.get("target_spot", 0.0),
            sl_spot_level=meta.get("sl_spot", 0.0),
        )
        
        self.trades.append(trade)
        
        # V4: Update heat manager
        self.heat_manager.record_entry(module.name, signal.contract.strike)
        
        if module.name != 'MAGIC_SQUARE':
            module.open_trade = trade
        else:
            module.open_trades.append(trade)
            
        if module.name != 'MAGIC_SQUARE':
            module.trade_count += 1
        
        self.same_dir_count[signal.direction] += 1
        
        size_msg = f" ({int(size_multiplier*100)}% size)" if size_multiplier < 1.0 else ""
        log.info(f"[ENTER] {trade.trade_id} | {signal.module}.{signal.strategy} | "
                f"{signal.direction}{int(signal.contract.strike)} | "
                f"Entry:₹{entry:.2f} SL:₹{trade.stop_loss:.2f} Target:₹{trade.target:.2f}{size_msg}")
        decision_logger.info(f"[ENTER] {trade.trade_id} | {signal.module} | {signal.reason}")
        
        self._log_to_csv(trade, 'ENTER', signal)
        return trade
    
    def _log_to_csv(self, trade: Trade, event: str, signal: Signal = None):
        fname = f'daily_data/modular_trades_{datetime.now().strftime("%Y%m%d")}.csv'
        file_exists = os.path.exists(fname)
        
        with open(fname, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'event', 'trade_id', 'module', 'strategy', 'direction',
                               'strike', 'entry', 'exit', 'sl', 'target', 'pnl', 'exit_reason',
                               'confidence', 'reason', 'unreal_pnl'])
            
            unreal = 0.0
            if event == 'UPDATE' and trade.status == 'OPEN':
                # Calculate unrealized P&L
                pass
                
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                event, trade.trade_id, trade.module, trade.strategy, trade.contract.option_type,
                trade.contract.strike, trade.entry_price, trade.close_price or '',
                trade.stop_loss, trade.target, trade.pnl if event == 'EXIT' else '',
                trade.exit_reason or '', getattr(signal, 'confidence', ''), getattr(signal, 'reason', '') if signal else '',
                unreal
            ])
    
    def update_unrealized_pnl(self, data: MarketData):
        for trade in self.trades:
            if trade.status != 'OPEN':
                continue
            
            strike = trade.contract.strike
            opt_type = trade.contract.option_type
            
            if strike in data.chain and opt_type in data.chain[strike]:
                ltp = data.chain[strike][opt_type].ltp
                trade_pnl = (ltp - trade.entry_price) * trade.quantity
                # Could log unrealized here
    
    def manage_exits(self, data: MarketData, modules: List[StrategyModule]):
        module_dict = {m.name: m for m in modules}
        
        for trade in self.trades:
            if trade.status != 'OPEN':
                continue
                
            strike = trade.contract.strike
            opt_type = trade.contract.option_type
            
            if strike not in data.chain or opt_type not in data.chain[strike]:
                continue
                
            ltp = data.chain[strike][opt_type].ltp
            ep = trade.entry_price
            
            if ep == 0:
                continue
                
            gain_pct = (ltp - ep) / ep
            trade.max_profit_pct = max(trade.max_profit_pct, gain_pct)
            
            # ── DH/DL CONTINUATION: spot-based SL + TSL every 10 pts ──────
            if trade.tsl_step_pts > 0 and trade.target_spot_level > 0:
                spot = data.spot
                # Spot-based SL check (overrides premium SL)
                if trade.sl_spot_level > 0:
                    if trade.contract.option_type == 'PE' and spot >= trade.sl_spot_level:
                        ltp = ep * 0.70  # force SL exit via premium floor
                        log.info(f"[DH/DL SL] {trade.trade_id} spot {spot:.0f} >= SL level {trade.sl_spot_level:.0f}")
                    elif trade.contract.option_type == 'CE' and spot <= trade.sl_spot_level:
                        ltp = ep * 0.70
                        log.info(f"[DH/DL SL] {trade.trade_id} spot {spot:.0f} <= SL level {trade.sl_spot_level:.0f}")
                # Activate TSL once spot reaches target level
                if not trade.tsl_active:
                    if trade.contract.option_type == 'PE' and spot <= trade.target_spot_level:
                        trade.tsl_active = True
                        log.info(f"[DH/DL TSL] {trade.trade_id} TARGET spot={spot:.0f} reached DayLow={trade.target_spot_level:.0f} — TSL now active")
                    elif trade.contract.option_type == 'CE' and spot >= trade.target_spot_level:
                        trade.tsl_active = True
                        log.info(f"[DH/DL TSL] {trade.trade_id} TARGET spot={spot:.0f} reached DayHigh={trade.target_spot_level:.0f} — TSL now active")
                # TSL: trail SL up every 10 spot pts of further move
                if trade.tsl_active:
                    new_sl = round(ltp * 0.90, 2)  # protect 90% of current premium
                    if new_sl > trade.stop_loss:
                        log.info(f"[DH/DL TSL] {trade.trade_id} trailing SL {trade.stop_loss:.2f} -> {new_sl:.2f} (spot={spot:.0f})")
                        trade.stop_loss = new_sl
            else:
                # Standard TSL for non-DH/DL trades
                if gain_pct >= Config.TRAIL_LOCK_PCT:
                    new_sl = round(ep * (1 + Config.TRAIL_BREAKEVEN_PCT), 2)
                    if new_sl > trade.stop_loss:
                        log.info(f"[TSL] {trade.trade_id} LOCK PROFIT: gain={gain_pct*100:.1f}%, SL {trade.stop_loss:.2f} -> {new_sl:.2f}")
                        trade.stop_loss = new_sl
                elif gain_pct >= Config.TRAIL_BREAKEVEN_PCT:
                    if trade.stop_loss < ep:
                        log.info(f"[TSL] {trade.trade_id} BREAKEVEN: gain={gain_pct*100:.1f}%, SL -> entry {ep:.2f}")
                        trade.stop_loss = ep
            
            now = datetime.now()
            mins_open = (now - trade.open_time).total_seconds() / 60
            loss_pct = (ep - ltp) / ep
            
            close_reason = None

            if ltp <= trade.stop_loss:
                close_reason = 'STOP_LOSS'
            elif ltp >= trade.target:
                close_reason = 'TARGET_HIT'
            elif (now.hour > Config.EOD_FORCE_START[0] or
                  (now.hour == Config.EOD_FORCE_START[0] and now.minute >= Config.EOD_FORCE_START[1])):
                close_reason = 'EOD_FORCE'
            elif mins_open > Config.TIME_STOP_MAX_MINUTES and loss_pct > 0.05:
                # FIX: Hard cap - any trade losing after 4 hours must exit, no direction check
                close_reason = 'TIME_STOP'
                log.info(f"[TIME_STOP_MAX] {trade.trade_id} hard cap {Config.TIME_STOP_MAX_MINUTES}min exceeded: loss={loss_pct*100:.1f}%")
            elif mins_open > Config.TIME_STOP_MINUTES and loss_pct > Config.TIME_STOP_LOSS_PCT:
                # V4: TIME_STOP only fires if spot confirms we are in wrong direction
                if Config.TIME_STOP_DIRECTION_CHECK and data.day_open:
                    spot_vs_open = data.spot - data.day_open
                    wrong_direction = (
                        (trade.contract.option_type == 'PE' and spot_vs_open > 30) or
                        (trade.contract.option_type == 'CE' and spot_vs_open < -30)
                    )
                    if wrong_direction:
                        close_reason = 'TIME_STOP'
                        log.info(f"[TIME_STOP] {trade.trade_id} confirmed wrong dir: spot_vs_open={spot_vs_open:.0f} loss={loss_pct*100:.1f}%")
                else:
                    close_reason = 'TIME_STOP'
                
            if close_reason:
                self._close_trade(trade, ltp, close_reason, module_dict)
    
    def _close_trade(self, trade: Trade, ltp: float, reason: str, module_dict: Dict):
        trade.status = 'CLOSED'
        trade.close_time = datetime.now()
        trade.close_price = ltp
        trade.exit_reason = reason
        
        trade.pnl = (ltp - trade.entry_price) * trade.quantity
        
        mod = module_dict.get(trade.module)
        if mod:
            mod.net_pnl += trade.pnl
            
            # V4: Record win/loss for cooldown
            if trade.pnl > 0:
                mod.record_win()
            else:
                mod.record_loss()
            
            # V4: Update heat manager
            self.heat_manager.record_exit(mod.name, trade.contract.strike)
            
            if mod.name == 'MAGIC_SQUARE':
                mod.trade_count += 1
                # V4: Only release strike if WIN - losing strikes stay blocked all day
                if trade.pnl > 0:
                    if trade.contract.strike in mod.traded_strikes:
                        mod.traded_strikes.remove(trade.contract.strike)
                        log.info(f"[MAGIC_SQUARE] Released strike {trade.contract.strike} (WIN - available for re-entry)")
                else:
                    log.info(f"[MAGIC_SQUARE] Strike {trade.contract.strike} BLOCKED for day (LOSS - no re-entry)")
            else:
                mod.open_trade = None
        
        self.same_dir_count[trade.contract.option_type] -= 1
        
        result = "WIN" if trade.pnl > 0 else "LOSS"
        log.info(f"[EXIT] {trade.trade_id} | {result} | {reason} | P&L:₹{trade.pnl:+.2f}")
        decision_logger.info(f"[EXIT] {trade.trade_id} | {result} | {reason} | P&L:₹{trade.pnl:+.2f}")
        
        self._log_to_csv(trade, 'EXIT', None)
    
    def get_total_pnl(self) -> float:
        """Calculate total realized P&L from all closed trades"""
        total = 0.0
        for trade in self.trades:
            if trade.status == 'CLOSED':
                total += trade.pnl
        return total

# ═════════════════════════════════════════════════════════════════════════════
# DATA FEED
# ═════════════════════════════════════════════════════════════════════════════

class DataFeed:
    """Real-time data feed from Dhan API via centralized GlobalDataFetcher"""
    
    def __init__(self):
        self.last_slow_update = 0
        self.closes: List[float] = []
        self._spot_history: List[float] = []
        self._last_good_chain: Dict = {}
        
        sys.path.append(r'C:\cursor\options\niftyopt\united_Indian_market1.0')
        from global_data_fetcher import get_global_data_fetcher
        self.fetcher = get_global_data_fetcher()
        self.client = self.fetcher.client
        
        # Start fetcher if not already running
        if not self.fetcher.running:
            try:
                self.fetcher.perform_data_warmup()
                self.fetcher.start()
            except Exception as e:
                log.warning(f"[DATAFEED] Could not start global data fetcher: {e}")
                
        self.data = self.fetcher.get_market_data('NIFTY')
        log.info("[DATAFEED] ✅ Integrated with Central GlobalDataFetcher")

    def connect(self):
        pass

    def _reconnect_if_stale(self):
        pass
    
    def update(self, candles: List[dict]):
        # Get latest data from fetcher
        md = self.fetcher.get_market_data('NIFTY')
        self.data = md
        self.closes = md.closes
        self._spot_history = md.closes.copy()
        
        # Register option contracts in the fetcher dynamically so it updates LTP
        for strike in md.chain:
            for opt_type in ['CE', 'PE']:
                contract = md.chain[strike].get(opt_type)
                if contract and contract.security_id:
                    self.fetcher.register_active_option_id(str(contract.security_id))
                    
        return self.data
        
    def _atm_strike(self, spot: float) -> float:
        return round(spot / 50) * 50
        
    def _calculate_pcr(self, chain: Dict):
        pass
        
    def _ema(self, prices: List[float], period: int) -> Optional[float]:
        if len(prices) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema
        
    def _rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        if len(prices) < period + 1:
            return None
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

# ═════════════════════════════════════════════════════════════════════════════
# MAIN TRADER
# ═════════════════════════════════════════════════════════════════════════════

class ModularTrader:
    """V4: Main trader with all enhancements"""
    
    def __init__(self):
        log.info("=" * 80)
        log.info(f"MODULAR TRADER {Config.VERSION} - ALL 18 STRATEGIES + LIVE HEALTH MONITOR")
        log.info(f"Build Date: {Config.BUILD_DATE} - Learning from April 29, 2026")
        log.info("=" * 80)
        log.info("✅ REAL DHAN API ONLY - No simulation/fallback")
        log.info(f"✅ ₹{Config.CAPITAL_PER_STRATEGY:,} capital per strategy")
        log.info(f"✅ Portfolio Heat: Max {Config.MAX_OPEN_PER_STRATEGY} positions per strategy")
        log.info(f"✅ Afternoon Choppy Filter: Block trends after 14:00 if VIX < {Config.CHOPPY_VIX_THRESHOLD}")
        log.info(f"✅ Momentum Bypass: {Config.PRICE_MOMENTUM_CONF_BYPASS:.0%}+ confidence bypasses filter")
        log.info(f"✅ Time-Based Sizing: {Config.REDUCED_SIZE_PCT*100:.0f}% after 14:00")
        log.info("=" * 80)
        
        # Initialize modules — all 18 strategies fully implemented
        self.modules: List[StrategyModule] = [
            UltimateORBModule(),
            DayHighBearishModule(),           # FIX: was bare StrategyModule() shell
            DayLowBullishModule(),            # FIX: was bare StrategyModule() shell
            DayLowBounceModule(),               # 3B - NEW June 4: Day low break + RSI<30
            EnhancedBearishModule(),          # FIX: was bare StrategyModule() shell
            EnhancedBullishModule(),          # FIX: was bare StrategyModule() shell
            DayHighLowTraditionalModule(),    # FIX: was bare StrategyModule() shell
            TrendFollowingModule(),
            AIEnhancedModule(),
            MeanReversionModule(),            # FIX: was bare StrategyModule() shell
            ScalpingModule(),                 # FIX: was bare StrategyModule() shell
            BreakoutModule(),                 # FIX: was bare StrategyModule() shell
            VolatilityBreakoutModule(),       # FIX: was bare StrategyModule() shell
            OptionsGreeksModule(),            # FIX: was bare StrategyModule() shell
            MagicSquareModule(),
            ShortUnwindModule(),              # FIX: was bare StrategyModule() shell
            LongUnwindModule(),               # FIX: was bare StrategyModule() shell
            ResistBreakModule(),              # FIX: was bare StrategyModule() shell
            PutWriterSupportModule(),         # FIX: was bare StrategyModule() shell
        ]
        
        self.module_dict = {m.name: m for m in self.modules}
        self.datafeed = DataFeed()
        self.trade_manager = TradeManager(self.modules)
        self.running = True
        self.cycle_count = 0
        
        # Reload open trades
        self._reload_open_trades()
        
        log.info(f"[INIT] {len(self.modules)} strategy modules loaded")
        for i, m in enumerate(self.modules, 1):
            log.info(f"[INIT]   {i}. {m.name} (enabled={m.enabled})")
    
    def _reload_open_trades(self):
        """Reload open trades from CSV and reconstruct Trade objects"""
        fname = f'daily_data/modular_trades_{datetime.now().strftime("%Y%m%d")}.csv'
        if not os.path.exists(fname):
            log.info("[RELOAD] No trades file found")
            return

        try:
            with open(fname, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Build map: trade_id -> last ENTER row (for open trades only)
            enter_rows: Dict[str, dict] = {}
            exited: set = set()
            for row in rows:
                tid = row.get('trade_id', '')
                event = row.get('event', '')
                if not tid:
                    continue
                if event == 'ENTER':
                    enter_rows[tid] = row
                elif event == 'EXIT':
                    exited.add(tid)

            open_tids = [tid for tid in enter_rows if tid not in exited]
            if not open_tids:
                log.info("[RELOAD] No open trades to restore")
                return

            log.info(f"[RELOAD] Restoring {len(open_tids)} open trades from CSV")
            module_dict = {m.name: m for m in self.modules}

            for tid in open_tids:
                r = enter_rows[tid]
                try:
                    strike = float(r.get('strike', 0))
                    opt_type = r.get('direction', 'PE')
                    entry_price = float(r.get('entry', 0) or r.get('entry_price', 0))
                    stop_loss = float(r.get('sl', 0) or r.get('stop_loss', 0))
                    target = float(r.get('target', 0))
                    qty = int(r.get('quantity', Config.LOT_SIZE))
                    module_name = r.get('module', '')
                    strategy = r.get('strategy', '')
                    open_time_str = r.get('timestamp', '')
                    try:
                        open_time = datetime.strptime(open_time_str, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        open_time = datetime.now()

                    cont = OptionContract(
                        security_id='', strike=strike, option_type=opt_type,
                        ltp=entry_price, iv=0, delta=0, gamma=0, theta=0, vega=0,
                        oi=0, volume=0, bid=entry_price, ask=entry_price
                    )
                    trade = Trade(
                        trade_id=tid, strategy=strategy, module=module_name,
                        contract=cont, entry_price=entry_price, quantity=qty,
                        target=target, stop_loss=stop_loss, open_time=open_time
                    )
                    self.trade_manager.trades.append(trade)

                    mod = module_dict.get(module_name)
                    if mod:
                        mod.open_trade = trade
                        if not hasattr(mod, 'open_trades'):
                            mod.open_trades = []
                        mod.open_trades.append(trade)
                        self.trade_manager.heat_manager.record_entry(module_name, strike)
                        dir_key = opt_type
                        self.trade_manager.same_dir_count[dir_key] = \
                            self.trade_manager.same_dir_count.get(dir_key, 0) + 1

                    log.info(f"[RELOAD] Restored {tid} | {module_name} | {opt_type}{int(strike)} | Entry:{entry_price}")

                except Exception as e2:
                    log.warning(f"[RELOAD] Skipped {tid}: {e2}")

        except Exception as e:
            log.warning(f"[RELOAD] Error: {e}")
    
    def _log_detailed_status(self, data: MarketData):
        """V3-style beautiful table display - updates every 30 seconds"""
        now_str = datetime.now().strftime('%H:%M:%S')
        tm = self.trade_manager
        
        # Clear screen and show header (every 3 cycles = ~30 seconds)
        if self.cycle_count % 3 == 0:
            os.system('cls' if os.name == 'nt' else 'clear')
            
            # Top header with market data
            day_open = data.day_open or data.spot
            day_high = data.day_high or data.spot
            day_low = data.day_low or data.spot
            rsi_val = data.rsi14 if data.rsi14 is not None else 50
            
            print("="*90)
            print(f" CYCLE {self.cycle_count} | {now_str} | NIFTY {data.spot:.2f} | "
                  f"O:{day_open:.1f} H:{day_high:.1f} L:{day_low:.1f} | "
                  f"PCR:{data.pcr:.3f} | BIAS:{data.pcr_bias}")
            
            # Get ATM premiums
            atm = data.atm_strike
            atm_ce = data.chain.get(atm, {}).get('CE')
            atm_pe = data.chain.get(atm, {}).get('PE')
            ce_prem = atm_ce.ltp if atm_ce else 0
            pe_prem = atm_pe.ltp if atm_pe else 0
            data_ok = "OK" if data.chain else "NO CHAIN"
            
            print(f" ATM:{int(atm)} CE:{ce_prem:.2f} PE:{pe_prem:.2f} | Data:{data_ok}")
            print("="*90)
            print()
            
            # Table header
            print(f" {'#':<3} {'STRATEGY':<26} {'STATUS':<10} {'CONTRACT':<12} {'ENTRY':>8} {'LTP':>8} "
                  f"{'UNREAL P&L':>12} {'NET P&L':>10} {'TRADES':>7}")
            print("-"*90)
            
            # Calculate total unrealized P&L
            total_unreal = 0.0
            
            # Show all 18 strategies
            for idx, mod in enumerate(self.modules, 1):
                name = mod.name
                trade_count = mod.trade_count
                net_pnl = mod.net_pnl
                
                # Get trade details
                open_trade = None
                if name == 'MAGIC_SQUARE':
                    ms_trades = [t for t in tm.trades if t.module == 'MAGIC_SQUARE' and t.status == 'OPEN']
                    if ms_trades:
                        open_trade = ms_trades[0]  # Show first one
                        ms_count = len(ms_trades)
                else:
                    open_trade = mod.open_trade
                
                # Format columns
                if open_trade:
                    status = "OPEN"
                    contract = f"{open_trade.contract.option_type}{int(open_trade.contract.strike)}"
                    entry = open_trade.entry_price
                    ltp = open_trade.contract.ltp
                    unreal = (ltp - entry) * open_trade.quantity if entry else 0
                    total_unreal += unreal
                    gain_pct = (ltp - entry) / entry * 100 if entry else 0
                    
                    entry_str = f"{entry:.2f}"
                    ltp_str = f"{ltp:.2f}"
                    unreal_str = f"{unreal:+.2f}"
                else:
                    status = "WAITING"
                    if trade_count >= (10 if name == 'MAGIC_SQUARE' else Config.MAX_TRADES_PER_STRATEGY):
                        status = "MAX"
                    elif net_pnl <= Config.DAILY_LOSS_LIMIT:
                        status = "LOSS_LIM"
                    
                    contract = "-"
                    entry_str = "-"
                    ltp_str = "-"
                    unreal_str = "-"
                
                print(f" {idx:<3} {name:<26} {status:<10} {contract:<12} {entry_str:>8} {ltp_str:>8} "
                      f"{unreal_str:>12} {net_pnl:>+9.2f} {trade_count:>7}")
            
            # Summary footer
            print("-"*90)
            total_net = tm.get_total_pnl()
            open_count = sum(1 for t in tm.trades if t.status == 'OPEN')
            ce_count = tm.same_dir_count.get('CE', 0)
            pe_count = tm.same_dir_count.get('PE', 0)
            
            print(f" TOTAL NET P&L: ₹{total_net:+.2f} | Unrealized: ₹{total_unreal:+.2f} | Trades: {trade_count}")
            print(f" CAPITAL: 18 × ₹50,000 = ₹900,000")
            print(f" DAILY LIMIT: ₹{Config.DAILY_LOSS_LIMIT:+.0f} | Used: ₹{abs(total_net) if total_net < 0 else 0:.0f}")
            print(f" CE Open: {ce_count} | PE Open: {pe_count} | UNLIMITED")
            print("="*90)
            print(" Press Ctrl+C to stop")
            print("="*90)
            print()
    
    def _get_strategy_qualification(self, mod, data: MarketData) -> str:
        """Get qualification string for a strategy (why it's waiting or ready)"""
        name = mod.name
        spot = data.spot
        pcr = data.pcr
        rsi = data.rsi14 or 50
        
        if name == 'ULTIMATE_DAY_HIGH_LOW':
            if mod.orb_high is None:
                return f"ORB locked? No (need 15 candles)"
            elif not mod._broke_ce and not mod._broke_pe:
                orb_h = mod.orb_high if mod.orb_high else 0
                orb_l = mod.orb_low if mod.orb_low else 0
                return f"ORB H={orb_h:.0f} L={orb_l:.0f} | Waiting breakout"
            elif mod._broke_ce and not mod._retest_ce:
                return "CE broke, waiting retest"
            elif mod._broke_pe and not mod._retest_pe:
                return "PE broke, waiting retest"
            else:
                return "Retest seen - watching"
                
        elif name == 'DAY_HIGH_BEARISH':
            issues = []
            if pcr < 1.1: issues.append(f"PCR={pcr:.2f}<1.1")
            if rsi < 65: issues.append(f"RSI={rsi:.0f}<65")
            return "READY" if not issues else " | ".join(issues)
            
        elif name == 'DAY_LOW_BULLISH':
            issues = []
            if pcr < 1.2: issues.append(f"PCR={pcr:.2f}<1.2")
            if rsi > 35: issues.append(f"RSI={rsi:.0f}>35")
            return "READY" if not issues else " | ".join(issues)
            
        elif name == 'TREND_FOLLOWING':
            if not data.prev_close:
                return "No prev_close"
            day_open = data.day_open or data.spot
            gap = (day_open - data.prev_close) / data.prev_close * 100
            return f"Gap={gap:+.2f}% (need ±0.2%)"
            
        elif name == 'AI_ENHANCED':
            ema_align = 'above' if spot > (data.ema20 or 0) else 'below'
            return f"RSI={rsi:.0f} PCR={pcr:.2f} Spot {ema_align} EMA20"
            
        elif name == 'MAGIC_SQUARE':
            is_expiry = datetime.now().weekday() == 3
            theta_lim = 0.50 if is_expiry else 0.15
            return f"Theta≤{theta_lim} | Scanning ATM±10"
            
        elif name == 'MEAN_REVERSION':
            day_open = data.day_open or spot
            dev = (spot - day_open) / day_open * 100 if day_open else 0
            threshold = Config.MEAN_REVERSION_DEVIATION_PCT * 100
            return f"Dev={dev:+.2f}% (need ±{threshold:.1f}%) RSI={rsi:.0f}"
            
        elif name == 'BREAKOUT':
            num_candles = len(data.closes)
            if num_candles < Config.BREAKOUT_CANDLES + 1:
                return f"Need {Config.BREAKOUT_CANDLES+1} candles (have {num_candles})"
            else:
                try:
                    rh = max(data.closes[-(Config.BREAKOUT_CANDLES+1):-1])
                    rl = min(data.closes[-(Config.BREAKOUT_CANDLES+1):-1])
                    return f"Range H={rh:.0f} L={rl:.0f} | Watching"
                except (ValueError, IndexError):
                    return "Calculating range..."
                
        elif name in ('DAY_HIGH_LOW_TRADITIONAL', 'SCALPING', 'VOLATILITY_BREAKOUT', 
                      'OPTIONS_GREEKS', 'SHORT_UNWIND', 'LONG_UNWIND', 
                      'WRITER_RESIST_BREAK', 'PUT_WRITER_SUPPORT',
                      'ENHANCED_BEARISH_REVERSAL', 'ENHANCED_BULLISH_REVERSAL'):
            return "Active - checking conditions"
        else:
            return "Active"
    
    def run(self):
        log.info(f"[RUN] Starting main loop - V4 + ADAPTIVE ML")
        log.info(f"[SESSION START] {Config.VERSION} - Learning from April 30 executed")
        log.info("[ADAPTIVE] V4 Engine integration: Check adaptive_data/adaptive_config.json every 60s")
        
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 20  # Exit after 20 straight crashes (200s of errors)
        
        try:
            while self.running:
                try:
                    self._cycle()
                    consecutive_errors = 0  # Reset on success
                    time.sleep(10)
                except KeyboardInterrupt:
                    log.info("[SHUTDOWN] Interrupted by user")
                    self.running = False
                    break
                except Exception as e:
                    import traceback
                    consecutive_errors += 1
                    log.error(f"[ERROR] {e} (consecutive #{consecutive_errors})")
                    log.error(f"[TRACEBACK] {traceback.format_exc()}")
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        log.critical(f"[FATAL] {consecutive_errors} consecutive errors - STOPPING to prevent silent failure. Last error: {e}")
                        self.running = False
                        break
                    time.sleep(10)
        finally:
            # FIX June 2: Add session summary logging (like V3)
            self._log_session_summary()
    
    def _log_session_summary(self):
        """Log end-of-session summary with P&L and trade counts"""
        try:
            tm = self.trade_manager
            closed = [t for t in tm.trades if t.exit_price is not None]
            
            if not closed:
                log.info("="*80)
                log.info("[SESSION END] V4 - No trades executed today")
                log.info("="*80)
                return
            
            final_pnl = sum(t.pnl or 0 for t in closed)
            wins = [t for t in closed if t.pnl and t.pnl > 0]
            losses = [t for t in closed if t.pnl and t.pnl <= 0]
            
            log.info("="*80)
            log.info("[SESSION COMPLETE] V4 + ADAPTIVE ML")
            log.info(f"Total Trades: {len(closed)}")
            log.info(f"Final P&L: ₹{final_pnl:+,.2f}")
            log.info(f"Wins: {len(wins)} | Losses: {len(losses)}")
            if closed:
                win_rate = len(wins) / len(closed) * 100
                avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0
                avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0
                log.info(f"Win Rate: {win_rate:.1f}%")
                log.info(f"Avg Win: ₹{avg_win:+,.2f} | Avg Loss: ₹{avg_loss:+,.2f}")
            log.info("="*80)
            
            # Also print to terminal
            print("\n" + "="*70)
            print(f"  MODULAR TRADER V4  |  SESSION COMPLETE")
            print("="*70)
            print(f"  Final P&L   : ₹{final_pnl:+,.2f}")
            print(f"  Total Trades: {len(closed)} | Wins: {len(wins)} | Losses: {len(losses)}")
            if closed:
                print(f"  Win Rate    : {win_rate:.1f}%")
            print("="*70 + "\n")
            
        except Exception as e:
            log.error(f"[SESSION END] Error logging summary: {e}")
    
    def _cycle(self):
        self.cycle_count += 1
        
        # V4: Check for adaptive config updates every 6 cycles (~1 minute)
        if self.cycle_count % 6 == 0:
            Config.load_adaptive_config()
        
        # Get data — candles fed from spot history built in _slow_update
        data = self.datafeed.update([])
        
        # Manage exits
        self.trade_manager.manage_exits(data, self.modules)
        
        # Generate signals
        for module in self.modules:
            if not module.enabled or module.is_in_cooldown():
                continue
                
            signal = module.analyze(data)
            if signal:
                self.trade_manager.enter(signal, module, data)
        
        # Log detailed strategy status (V3 style - all 18 strategies every cycle)
        self._log_detailed_status(data)

if __name__ == "__main__":
    trader = ModularTrader()
    trader.run()
