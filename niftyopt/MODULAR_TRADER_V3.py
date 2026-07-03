#!/usr/bin/env python3
"""
MODULAR TRADER V3 - ALL 18 STRATEGIES + LIVE HEALTH MONITOR
=============================================================
V3 Changes from V2 (April 28 2026 audit):
  Strategy fixes:
    1.  ULTIMATE_DAY_HIGH_LOW    - ORB now 15-min candles (9:15-9:30), static levels, retest before entry
    2.  DAY_HIGH_BEARISH         - PCR >= 1.1 (was <0.85), RSI > 65 required, retest confirmation
    3.  DAY_LOW_BULLISH          - PCR >= 1.2 (was <=1.15), RSI < 35 required, double-bottom confirmation
    4.  ENHANCED_BEARISH_REVERSAL- Unchanged (working correctly)
    5.  ENHANCED_BULLISH_REVERSAL- PCR >= 1.2 (was <=1.10)
    6.  DAY_HIGH_LOW_TRADITIONAL - 15-min high/low range + retest, replaces EMA-every-cycle
    7.  TREND_FOLLOWING          - Unchanged (correct behavior)
    8.  AI_ENHANCED              - Unchanged (working correctly)
    9.  MEAN_REVERSION           - Threshold 1.5% -> 0.5% (NIFTY-calibrated)
    10. SCALPING                 - 5 consecutive candles (was 3) + 2x momentum + 15pt move
    11. BREAKOUT                 - Retest confirmation added (was immediate on breakout)
    12. VOLATILITY_BREAKOUT      - ATM-only IV (was all-chain average, diluted by OTM)
    13. OPTIONS_GREEKS           - EMA20 price-direction filter added
    14. MAGIC_SQUARE             - Theta limit 0.50 on Thursdays (expiry day), 0.15 otherwise
    15. SHORT_UNWIND             - Unchanged (correct behavior)
    16. LONG_UNWIND              - Unchanged (correct behavior)
    17. WRITER_RESIST_BREAK      - Unchanged (correct behavior)
    18. PUT_WRITER_SUPPORT       - Support-break invalidation added (day_low < level-10)
  Infrastructure:
    + LiveHealthMonitor thread - per-cycle one-line qualification of every strategy
    + Trade state reload on startup (fixes orphan ghost trades on restart)
    + Duplicate run() removed
"""

import json, time, logging, csv, os, math, threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
sys.path.insert(0, r'c:\cursor\options\niftyopt\Lib\site-packages')
from dhanhq import dhanhq

# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

class Config:
    """Central configuration"""
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
    TARGET_PCT_HIGH_CONF = 1.00  # FIX June 9: 100% target for high confidence (was 50% = too early exits)
    CAPITAL_PER_STRATEGY = 50_000
    HIGH_CONFIDENCE_SIZE_MULTIPLIER = 4.0  # FIX June 9: 4x size on confidence >0.90 (₹2K → ₹8K per trade)
    
    # Time Windows
    MARKET_OPEN = (9, 15)
    MARKET_CLOSE = (15, 15)  # Changed from 15:25 to 15:15 for intraday square-off
    NO_ENTRY_BEFORE = (9, 30)
    NO_ENTRY_AFTER = (15, 0)  # Extended to 3:00 PM for afternoon opportunities (was 2:30)
    
    # PCR (using original file's exact thresholds)
    PCR_BULLISH = 0.75      # For PCR_BULLISH strategy (was 0.85)
    PCR_BEARISH = 1.25      # For PCR_BEARISH strategy (was 1.15)
    PCR_REVERSAL_THRESH = 0.85  # For day high/low reversal
    PCR_STABILITY_CYCLES = 3
    PCR_OI_IMBALANCE_PCT = 0.20
    
    # Magic Squares
    MAGIC_SQUARES = [9, 36, 81, 144, 225, 324, 441, 576]
    LOT_MULTIPLIERS = {9: 2.5, 36: 2.0, 81: 2.0, 144: 1.5, 225: 1.5, 324: 1.0, 441: 1.0, 576: 1.0}
    
    # Risk Management
    MAX_TRADES_PER_STRATEGY = 3
    MAX_SAME_DIR_OPEN = 2
    DAILY_PROFIT_TARGET = 2_500
    DAILY_LOSS_LIMIT = -5_000   # Per-strategy daily loss limit (was -1500, too tight)
    PORTFOLIO_LOSS_LIMIT = -10_000  # FIX June 3: Tightened -20K→-10K (June 3 hit -29K, should have stopped at -10K)
    MIN_ENTRY_PREMIUM = 15.0   # FIX 2026-05-19: Block near-zero premium (deep OTM / decay)
    
    # Trail Stops
    TRAIL_BREAKEVEN_PCT = 0.20
    TRAIL_LOCK_PCT = 0.35
    TIME_STOP_MINUTES = 120    # V3 FIX: 2hr time-stop (was 1hr - May 27 had 4 TIME_STOP losses at 60min)
    TIME_STOP_LOSS_PCT = 0.15   # V3 FIX: Exit if down 15%+ after 1hr (was 25% = held all day)
    DECAY_STOP_PCT = 0.005
    DECAY_STOP_CONSEC = 5
    
    # Delta Range
    MIN_DELTA = 0.30
    MAX_DELTA = 0.65
    
    # Magic Square delta range (wider - allow more OTM options)
    MAGIC_MIN_DELTA = 0.10  # Allow deeper OTM for magic square
    MAGIC_MAX_DELTA = 0.80  # Allow deeper ITM for magic square
    MAGIC_TOLERANCE_PCT = 0.05  # 5% tolerance for premium match (was 1.5%)
    MAGIC_MAX_TRADES = 2        # V3 FIX: Max 2 Magic Square trades/day (May 27: 5 entries, all lost)
    MAGIC_MAX_OPEN_SIMULTANEOUS = 1  # FIX June 8: Only 1 MAGIC_SQUARE open at a time (today: 6 simultaneous = -26K)
    
    # NEW: Direction Filter - Block trades opposite to market bias
    DIRECTION_FILTER_ENABLED = True  # Enable bias-based filtering
    DIRECTION_FILTER_CONFIDENCE = 0.70  # Only filter high-confidence signals
    
    # FIX: Gap Recovery Filter - Stop new PE entries when gap-down day reverses
    GAP_RECOVERY_ENABLED = True
    GAP_RECOVERY_THRESHOLD = 0.001  # Block PE when spot within 0.1% of open (recovered)
    GAP_RECOVERY_AFTER_MINUTES = 60  # Apply only after 60min (10:15+)
    GAP_RECOVERY_MIN_GAP_PCT = 0.005  # Only trigger on real gap-down days (>0.5% gap)

    # NEW: Gap-Day Override - Allow trades against PCR bias on gap days (first 30 min)
    GAP_DAY_OVERRIDE_ENABLED = True  # Enable gap-day override
    GAP_DAY_OVERRIDE_MINUTES = 30  # Window after open to override PCR filter
    GAP_DOWN_THRESHOLD = -50  # Points gap down to trigger override (PE trades)
    GAP_UP_THRESHOLD = 50  # Points gap up to trigger override (CE trades)
    
    # NEW: Price Momentum Filter - Block trades against strong price movement
    PRICE_MOMENTUM_ENABLED = True  # Enable price-based filtering
    PRICE_MOMENTUM_THRESHOLD = 20  # FIX June 8: 20pts threshold (was 30) - today lost -26K trading CE on bearish day
    
    # NEW: VWAP Chop Filter - Avoid entries when price is near VWAP (choppy zone)
    VWAP_CHOP_FILTER_ENABLED = True
    VWAP_CHOP_BAND_PCT = 0.002  # Block trades within 0.2% of VWAP (choppy zone)
    
    # NEW: Strike Diversification
    MAX_TRADES_PER_STRIKE = 3  # Max 3 strategies per strike
    
    # NEW: Time-Based Strategy Selection
    MORNING_WINDOW = (9, 30, 11, 0)      # 9:30-11:00 - Reversal strategies
    MIDDAY_WINDOW = (11, 0, 13, 0)        # 11:00-13:00 - Trend following
    AFTERNOON_WINDOW = (13, 0, 15, 15)   # 13:00-15:15 - Momentum strategies
    
    # Strategy-specific
    ORB_CANDLES = 45
    BREAKOUT_CANDLES = 72
    SCALPING_CANDLES = 15
    AI_MIN_CANDLES = 30
    IV_THRESHOLD = 18.0  # FIX June 4: Raised back to 18.0 - today's VOL_BREAKOUT trade lost -₹7,215 at VIX 15.8

# ═════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═════════════════════════════════════════════════════════════════════════════

os.makedirs('daily_data', exist_ok=True)
today_str = datetime.now().strftime('%Y%m%d')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(f'daily_data/v3_{today_str}.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

decision_logger = logging.getLogger('decisions')
decision_logger.setLevel(logging.INFO)
decision_handler = logging.FileHandler(f'daily_data/v3_decisions_{today_str}.log', encoding='utf-8')
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
    status: str = 'OPEN'
    exit_price: float = 0.0
    pnl: float = 0.0
    close_time: Optional[datetime] = None
    exit_reason: str = ''
    _decay_consec: int = 0
    _prev_ltp: float = 0.0
    max_profit_pct: float = 0.0
    unreal_pnl: float = 0.0

@dataclass
class Signal:
    module: str
    strategy: str
    direction: str
    contract: OptionContract
    confidence: float
    reason: str

# ═════════════════════════════════════════════════════════════════════════════
# DATA FEED MODULE
# ═════════════════════════════════════════════════════════════════════════════

class DataFeed:
    """Single data feed - fetches from Dhan API via centralized GlobalDataFetcher"""
    
    def __init__(self):
        self._lock = threading.Lock()
        
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
    
    def _connect(self):
        pass
    
    def get_current_data(self) -> MarketData:
        with self._lock:
            # Get latest data from central fetcher
            md = self.fetcher.get_market_data('NIFTY')
            self.data = md
            return self._copy_data()
            
    @property
    def data_age_secs(self) -> float:
        """Seconds since last full update."""
        with self._lock:
            return (datetime.now() - self.data.timestamp).total_seconds()
            
    def _copy_data(self) -> MarketData:
        return MarketData(
            timestamp=self.data.timestamp, spot=self.data.spot,
            day_open=self.data.day_open, day_high=self.data.day_high,
            day_low=self.data.day_low, prev_close=self.data.prev_close,
            vix=self.data.vix, closes=self.data.closes.copy(),
            chain=self.data.chain.copy(), pcr=self.data.pcr,
            pcr_bias=self.data.pcr_bias, pcr_zone_count=self.data.pcr_zone_count,
            pcr_raw_zone=self.data.pcr_raw_zone, vwap=self.data.vwap,
            ema5=self.data.ema5, ema20=self.data.ema20, rsi14=self.data.rsi14,
            atm_strike=self.data.atm_strike,
            max_call_oi_strike=self.data.max_call_oi_strike,
            max_put_oi_strike=self.data.max_put_oi_strike,
            prev_oi_state=self.data.prev_oi_state.copy(),
            prev_spot=self.data.prev_spot,
            put_oi_total=self.data.put_oi_total,
            call_oi_total=self.data.call_oi_total
        )
        
    def fast_update(self) -> bool:
        # Register option contracts in the fetcher dynamically so it updates LTP
        md = self.fetcher.get_market_data('NIFTY')
        for strike in md.chain:
            for opt_type in ['CE', 'PE']:
                contract = md.chain[strike].get(opt_type)
                if contract and contract.security_id:
                    self.fetcher.register_active_option_id(str(contract.security_id))
        return True

    def update(self) -> bool:
        # Register option contracts in the fetcher dynamically so it updates LTP
        md = self.fetcher.get_market_data('NIFTY')
        for strike in md.chain:
            for opt_type in ['CE', 'PE']:
                contract = md.chain[strike].get(opt_type)
                if contract and contract.security_id:
                    self.fetcher.register_active_option_id(str(contract.security_id))
        return True
        
    def _fetch_option_chain(self, spot: float) -> Tuple[Dict, str]:
        return {}, ''
        
    @staticmethod
    def _calc_pcr_bias(pcr: float, put_oi: int, call_oi: int, 
                       zone_count: int, raw_zone: str) -> Tuple[str, int, str]:
        return 'NEUTRAL', 0, 'NEUTRAL'
        
    @staticmethod
    def _calc_ema(closes: List[float], period: int) -> Optional[float]:
        return None
        
    @staticmethod
    def _calc_rsi(closes: List[float], period: int = 14) -> Optional[float]:
        return None
        
    @staticmethod
    def _max_oi_strike(chain: Dict, side: str) -> Optional[float]:
        return None

# ═════════════════════════════════════════════════════════════════════════════
# STRIKE SELECTION HELPER - Premium < 500 only (not strike distance)
# ═════════════════════════════════════════════════════════════════════════════

def filter_chain_by_premium(chain: Dict, side: str, max_premium: float = 500) -> Dict:
    """Filter chain to only include contracts with premium < max_premium"""
    filtered = {}
    for strike, data in chain.items():
        opt = data.get(side)
        if opt and opt.ltp < max_premium:
            filtered[strike] = data
    return filtered

def best_contract_premium_filtered(data: MarketData, side: str,
                                      delta_min: float = 0.30, delta_max: float = 0.65,
                                      max_premium: float = 500) -> Optional[OptionContract]:
    """Select best contract with premium < 500"""
    # Filter chain to only contracts with premium < 500
    filtered_chain = filter_chain_by_premium(data.chain, side, max_premium)

    candidates = [filtered_chain[s][side] for s in filtered_chain
                  if side in filtered_chain[s] and delta_min <= abs(filtered_chain[s][side].delta) <= delta_max]
    if not candidates:
        # Fallback: try with wider delta range
        candidates = [filtered_chain[s][side] for s in filtered_chain
                      if side in filtered_chain[s] and 0.20 <= abs(filtered_chain[s][side].delta) <= 0.75]
    if not candidates:
        return None

    max_vol = max(c.volume for c in candidates) or 1
    max_oi = max(c.oi for c in candidates) or 1
    return max(candidates, key=lambda c: abs(c.delta) * 0.4 + (c.volume / max_vol) * 0.3 + (c.oi / max_oi) * 0.3)

# ═════════════════════════════════════════════════════════════════════════════
# ALL 18 STRATEGY MODULES
# ═════════════════════════════════════════════════════════════════════════════

class StrategyModule:
    """Base class for all 17 strategy modules"""
    
    def __init__(self, name: str, display_name: str):
        self.name = name
        self.display_name = display_name
        self.enabled = True
        self.trade_count = 0
        self.net_pnl = 0.0
        self.open_trade: Optional[Trade] = None
    
    def analyze(self, data: MarketData) -> Optional[Signal]:
        return None
    
    def reset_daily(self):
        self.trade_count = 0
        self.net_pnl = 0.0

# ── Strategy 1: ULTIMATE_DAY_HIGH_LOW (ORB-15min) ───────────────────────────
class UltimateDayHighLowModule(StrategyModule):
    """Strategy 1: Opening Range Breakout - first 15 one-minute candles (9:15-9:30)
    ORB high/low locked once at candle 15, never updated.
    Entry only after a retest of the breakout level (price pulls back then breaks again)."""
    def __init__(self):
        super().__init__("ULTIMATE_DAY_HIGH_LOW", "ULTIMATE_DAY_HIGH_LOW")
        self.orb_high: Optional[float] = None
        self.orb_low: Optional[float] = None
        self.ce_fired = False
        self.pe_fired = False
        self._broke_ce = False   # first breakout above ORB high seen
        self._broke_pe = False   # first breakdown below ORB low seen
        self._retest_ce = False  # price pulled back within 0.3% of ORB high after breakout
        self._retest_pe = False  # price pulled back within 0.3% of ORB low after breakdown

    def analyze(self, data: MarketData) -> Optional[Signal]:
        # Lock ORB levels after exactly 15 one-minute candles
        if self.orb_high is None:
            if len(data.closes) >= 15:
                self.orb_high = max(data.closes[:15])
                self.orb_low  = min(data.closes[:15])
                log.info(f"[ORB] Levels locked: High={self.orb_high:.2f} Low={self.orb_low:.2f}")
            return None

        spot = data.spot

        # ── CE side: breakout above ORB high, wait for retest, then enter ──
        if not self.ce_fired:
            if not self._broke_ce:
                if spot > self.orb_high * 1.002:  # clean breakout 0.2% above
                    self._broke_ce = True
                    log.info(f"[ORB] CE breakout: spot={spot:.0f} > ORB_HIGH={self.orb_high:.0f}")
            elif not self._retest_ce:
                # V3 TUNING: On strong trend days (>100pts up from open), shallow pullback is enough
                strong_trend = data.day_open and (spot - data.day_open) > 100
                retest_threshold = self.orb_high * 1.0015 if strong_trend else self.orb_high * 1.001
                if spot <= retest_threshold:
                    self._retest_ce = True
                    log.info(f"[ORB] CE retest: spot={spot:.0f} pulled back to ORB_HIGH={self.orb_high:.0f} {'(trend-relaxed)' if strong_trend else ''}")
            else:
                if spot > self.orb_high * 1.001:  # re-broke above after retest
                    self.ce_fired = True
                    c = self._best_contract(data, 'CE', delta_min=0.40, delta_max=0.70)
                    if c:
                        return Signal(self.name, "ORB_BREAKOUT_CE", "CE", c, 0.88,
                                    f"ORB15 high {self.orb_high:.0f} broke-retest-confirmed")

        # ── PE side: breakdown below ORB low, wait for retest, then enter ──
        if not self.pe_fired:
            if not self._broke_pe:
                if spot < self.orb_low * 0.998:  # clean breakdown
                    self._broke_pe = True
                    log.info(f"[ORB] PE breakdown: spot={spot:.0f} < ORB_LOW={self.orb_low:.0f}")
            elif not self._retest_pe:
                if spot >= self.orb_low * 0.999:  # pulled back to level
                    self._retest_pe = True
                    log.info(f"[ORB] PE retest: spot={spot:.0f} pulled back to ORB_LOW={self.orb_low:.0f}")
            else:
                if spot < self.orb_low * 0.999:  # re-broke below after retest
                    self.pe_fired = True
                    c = self._best_contract(data, 'PE', delta_min=0.40, delta_max=0.70)
                    if c:
                        return Signal(self.name, "ORB_BREAKOUT_PE", "PE", c, 0.88,
                                    f"ORB15 low {self.orb_low:.0f} broke-retest-confirmed")
        return None

    def _best_contract(self, data: MarketData, side: str, delta_min=0.30, delta_max=0.65) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ── Strategy 2: DAY_HIGH_BEARISH ───────────────────────────────────────────
class DayHighBearishModule(StrategyModule):
    """Strategy 2: Day high bearish reversal.
    Uses 15-min ORB high (first 15 candles). Requires a retest of day high before entry.
    PCR fix: requires PCR >= 1.1 (bearish sentiment) not < 0.85."""
    def __init__(self):
        super().__init__("DAY_HIGH_BEARISH", "DAY_HIGH_BEARISH")
        self._session_high: Optional[float] = None
        self._locked_at_candle = 15
        self._touched_high = False   # price touched day high
        self._retested = False       # price pulled back from high

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.day_high:
            return None
        # Lock session high from 15-min ORB candles
        if self._session_high is None and len(data.closes) >= self._locked_at_candle:
            self._session_high = max(data.closes[:self._locked_at_candle])
        ref_high = self._session_high if self._session_high else data.day_high

        # PCR must be bearish (>= 1.1) to confirm sellers in control
        if data.pcr < 1.1:
            return None
        # RSI must be overbought
        if not data.rsi14 or data.rsi14 < 65:
            return None

        spot = data.spot
        # Step 1: price touches near day high
        if not self._touched_high:
            if spot >= ref_high * 0.997:
                self._touched_high = True
        # Step 2: price pulls back (retest)
        elif not self._retested:
            if spot < ref_high * 0.996:
                self._retested = True
        # Step 3: price bounces back up to high again → confirmed rejection → sell
        else:
            if spot >= ref_high * 0.997:
                self._touched_high = False  # reset for next cycle
                self._retested = False
                c = best_contract_premium_filtered(data, 'PE', delta_min=0.45, delta_max=0.65, max_premium=500)
                if c:
                    return Signal(self.name, "DAY_HIGH_REVERSAL", "PE", c, 0.75,
                                f"Day high {ref_high:.0f} retest rejected PCR={data.pcr:.2f} RSI={data.rsi14:.0f}")
        return None

    def _best_contract(self, data: MarketData, side: str, delta_min=0.45, delta_max=0.65) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ── Strategy 3: DAY_LOW_BULLISH ──────────────────────────────────────────────
class DayLowBullishModule(StrategyModule):
    """Strategy 3: Day low bullish reversal.
    Uses 15-min ORB low. Requires retest + bounce confirmation.
    PCR fix: requires PCR >= 1.2 (put writers defending = bullish) not <= 1.15."""
    def __init__(self):
        super().__init__("DAY_LOW_BULLISH", "DAY_LOW_BULLISH")
        self._session_low: Optional[float] = None
        self._locked_at_candle = 15
        self._touched_low = False
        self._retested = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.day_low:
            return None
        if self._session_low is None and len(data.closes) >= self._locked_at_candle:
            self._session_low = min(data.closes[:self._locked_at_candle])
        ref_low = self._session_low if self._session_low else data.day_low

        # V3 TUNING: Loosened PCR requirement - RSI oversold alone is strong signal
        # Original: PCR >= 1.2 + RSI <= 35 (too strict on gap-up recovery days)
        # New: RSI <= 30 can fire without PCR, OR PCR >= 0.9 + RSI <= 35
        if not data.rsi14:
            return None
        if data.rsi14 <= 30:
            pass  # Deeply oversold - strong enough signal alone
        elif data.rsi14 <= 35 and data.pcr >= 0.9:
            pass  # Mildly oversold + supportive PCR
        else:
            return None

        spot = data.spot
        # Step 1: price touches near day low
        if not self._touched_low:
            if spot <= ref_low * 1.003:
                self._touched_low = True
        # Step 2: price bounces up (retest from below)
        elif not self._retested:
            if spot > ref_low * 1.004:
                self._retested = True
        # Step 3: price dips back to low again → double-bottom confirmed → buy
        else:
            if spot <= ref_low * 1.003:
                self._touched_low = False
                self._retested = False
                c = best_contract_premium_filtered(data, 'CE', delta_min=0.45, delta_max=0.65, max_premium=500)
                if c:
                    return Signal(self.name, "DAY_LOW_REVERSAL", "CE", c, 0.75,
                                f"Day low {ref_low:.0f} double-bottom PCR={data.pcr:.2f} RSI={data.rsi14:.0f}")
        return None

    def _best_contract(self, data: MarketData, side: str, delta_min=0.45, delta_max=0.65) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ── Strategy 3B: DAY_LOW_BOUNCE (NEW June 4) ───────────────────────────────
class DayLowBounceModule(StrategyModule):
    """Strategy 3B: Day low bounce - when day_low is broken but RSI < 30.
    June 4 Learning: Today day_low=23247, RSI=16 - perfect setup missed.
    Enters CE when price breaks day_low with extreme oversold RSI."""
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
    
    def _best_contract(self, data: MarketData, side: str, delta_min=0.40, delta_max=0.65) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ── Strategy 4: ENHANCED_BEARISH_REVERSAL ──────────────────────────────────
class EnhancedBearishModule(StrategyModule):
    """Strategy 4: Enhanced bearish with RSI"""
    def __init__(self):
        super().__init__("ENHANCED_BEARISH_REVERSAL", "ENHANCED_BEARISH_REVERSAL")
        self._fired_today = False  # FIX: max 1 entry per day - no repeated SL re-entries

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
    
    def _best_contract(self, data: MarketData, side: str, delta_min=0.45, delta_max=0.65) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ── Strategy 5: ENHANCED_BULLISH_REVERSAL ──────────────────────────────────
class EnhancedBullishModule(StrategyModule):
    """Strategy 5: Enhanced bullish with RSI.
    PCR fix: requires PCR >= 1.2 (put writers active = bullish bias), not <= 1.10."""
    def __init__(self):
        super().__init__("ENHANCED_BULLISH_REVERSAL", "ENHANCED_BULLISH_REVERSAL")
        self._fired_today = False  # FIX: max 1 entry per day - no repeated SL re-entries

    def reset_daily(self):
        super().reset_daily()
        self._fired_today = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if self._fired_today:  # FIX: one shot per day
            return None
        if not data.day_low or data.spot > data.day_low * 1.005:
            return None
        # V3 TUNING: Loosened - RSI deeply oversold is strong enough alone
        if not data.rsi14:
            return None
        if data.rsi14 <= 30:
            pass  # Deeply oversold near day low - strong reversal signal alone
        elif data.rsi14 <= 35 and data.pcr >= 0.9:
            pass  # Mildly oversold + supportive PCR
        else:
            return None
        
        # FIX: Tightened from -50 to -25pts - May 26 lesson: market at -30pts still triggers wrong CE
        if data.day_open and (data.spot - data.day_open) < -25:
            log.info(f"[ENHANCED_BULL] Skipping CE - market DOWN {data.day_open - data.spot:.0f}pts from open (bearish day, RSI={data.rsi14:.1f})")
            return None
        
        c = best_contract_premium_filtered(data, 'CE', delta_min=0.45, delta_max=0.65, max_premium=500)
        if c:
            self._fired_today = True
            return Signal(self.name, "ENHANCED_BULLISH", "CE", c, 0.75,
                        f"Low {data.day_low:.0f} RSI={data.rsi14:.1f} PCR={data.pcr:.3f}")
        return None
    
    def _best_contract(self, data: MarketData, side: str, delta_min=0.45, delta_max=0.65) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ── Strategy 6: DAY_HIGH_LOW_TRADITIONAL ───────────────────────────────────────
class DayHighLowTraditionalModule(StrategyModule):
    """Strategy 6: 15-min range breakout with retest confirmation.
    Locks the high/low of the first 15 one-minute candles (9:15-9:30).
    Fires only on a retest of the breakout level, not on first touch."""
    def __init__(self):
        super().__init__("DAY_HIGH_LOW_TRADITIONAL", "DAY_HIGH_LOW_TRADITIONAL")
        self._range_high: Optional[float] = None
        self._range_low: Optional[float] = None
        self._broke_up = False
        self._broke_dn = False
        self._retest_up = False
        self._retest_dn = False
        self.ce_fired = False
        self.pe_fired = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        # Lock 15-min high/low once
        if self._range_high is None:
            if len(data.closes) >= 15:
                self._range_high = max(data.closes[:15])
                self._range_low  = min(data.closes[:15])
                log.info(f"[DHLTrad] 15-min range locked: H={self._range_high:.2f} L={self._range_low:.2f}")
            return None

        spot = data.spot

        # ── CE: breakout above 15-min high + retest ──
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
                    c = self._best_contract(data, 'CE')
                    if c:
                        return Signal(self.name, "RANGE_BREAK_CE", "CE", c, 0.70,
                                    f"15min high {self._range_high:.0f} retest confirmed")

        # ── PE: breakdown below 15-min low + retest ──
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
                    c = self._best_contract(data, 'PE')
                    if c:
                        return Signal(self.name, "RANGE_BREAK_PE", "PE", c, 0.70,
                                    f"15min low {self._range_low:.0f} retest confirmed")
        return None

    def _best_contract(self, data: MarketData, side: str) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)

# ── Strategy 7: TREND_FOLLOWING ─────────────────────────────────────────────
class TrendFollowingModule(StrategyModule):
    """Strategy 7: Trend following with open/prev_close gaps.
    P1 fix: Cancel if gap reversed >50%. P5 fix: Block after 11:00 if gap reversed."""
    def __init__(self):
        super().__init__("TREND_FOLLOWING", "TREND_FOLLOWING")
    
    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.day_open or not data.prev_close:
            return None
        
        gap = data.day_open - data.prev_close          # original gap at open
        gap_pct = gap / data.prev_close
        
        # V3 TUNING: Lowered gap threshold from 0.2% to 0.15% (~35 NIFTY pts)
        # May 15 missed: gap was +0.18% (43pts) = genuine trend day, blocked at 0.2%
        if abs(gap_pct) < 0.0015:
            return None
        
        # P1: How much of the gap has been recovered by current spot?
        # If spot has moved back > 50% of the original gap direction → gap reversed, skip
        spot_move_from_open = data.spot - data.day_open
        gap_recovered_pct = (spot_move_from_open / gap) if gap != 0 else 0  # positive = recovering gap
        if gap_recovered_pct > 0.50:
            log.info(f"[TREND] Gap {'up' if gap>0 else 'down'} {gap:.0f}pts but spot recovered {gap_recovered_pct*100:.0f}% - skipping")
            return None
        
        now = datetime.now()
        
        uptrend = gap_pct >= 0.0015 and data.spot > data.day_open * 1.0015
        downtrend = gap_pct <= -0.0015 and data.spot < data.day_open * 0.9985
        
        # P5: After 11:00, only allow if gap still fully intact (not reversed at all)
        if now.hour >= 11:
            if uptrend and spot_move_from_open < 0:     # spot slipped below open
                return None
            if downtrend and spot_move_from_open > 0:   # spot recovered above open
                return None
        
        if uptrend:
            c = self._best_contract(data, 'CE')
            if c:
                return Signal(self.name, "GAP_UP_TREND", "CE", c, 0.70,
                            f"Gap up trend: open {data.day_open:.0f} > prev {data.prev_close:.0f}")
        
        if downtrend:
            c = self._best_contract(data, 'PE')
            if c:
                return Signal(self.name, "GAP_DOWN_TREND", "PE", c, 0.70,
                            f"Gap down trend: open {data.day_open:.0f} < prev {data.prev_close:.0f}")
        return None
    
    def _best_contract(self, data: MarketData, side: str) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)

# ── Strategy 8: AI_ENHANCED ────────────────────────────────────────────────
class AIEnhancedModule(StrategyModule):
    """Strategy 8: Multi-indicator ensemble (weighted score)"""
    def __init__(self):
        super().__init__("AI_ENHANCED", "AI_ENHANCED")
    
    def analyze(self, data: MarketData) -> Optional[Signal]:
        if len(data.closes) < Config.AI_MIN_CANDLES:
            return None
        if not data.rsi14 or not data.ema20:
            return None
        
        # Momentum: % change over last 5 candles
        mom = (data.closes[-1] - data.closes[-6]) / data.closes[-6] * 100 if len(data.closes) >= 6 else 0
        
        # Candle body score last 3 candles
        body_score = sum(1 if data.closes[i] > data.closes[i-1] else -1 for i in range(-3, 0))
        
        # Weighted bullish score (0-1)
        rsi_bull = max(0, (data.rsi14 - 50) / 50)
        pcr_bull = max(0, (1.0 - data.pcr) / 0.5)
        mom_bull = max(0, min(1, mom / 2.0))
        ema_bull = 1.0 if data.spot > data.ema20 else 0.0
        body_bull = max(0, body_score / 3)
        
        bull_score = (rsi_bull * 0.25 + pcr_bull * 0.25 + mom_bull * 0.20 +
                      ema_bull * 0.20 + body_bull * 0.10)
        bear_score = 1.0 - bull_score
        
        # P2: Raise threshold to 0.75 (was 0.65) - require stronger conviction
        # P2: Also block PE if spot is 50+ pts above day_open (market clearly bullish)
        # P2: Also block CE if spot is 50+ pts below day_open (market clearly bearish)
        spot_vs_open = (data.spot - data.day_open) if data.day_open else 0
        
        # P2 FIX: Raised to 0.80 (was 0.75) - May 27: 0.94 AI confidence still lost
        if bull_score >= 0.80:
            if spot_vs_open < -50:   # market down 50pts - block bullish AI entry
                log.info(f"[AI] Blocking CE - AI bullish {bull_score:.2f} but market down {spot_vs_open:.0f}pts")
                return None
            c = self._best_contract(data, 'CE')
            if c:
                return Signal(self.name, "AI_BULLISH", "CE", c, bull_score,
                            f"AI score: bullish {bull_score:.2f}")
        
        if bear_score >= 0.80:
            if spot_vs_open > 30:    # FIX 2026-05-19: lowered 50→30pts (was too loose, fired 3× losses)
                log.info(f"[AI] Blocking PE - AI bearish {bear_score:.2f} but market up {spot_vs_open:.0f}pts")
                return None
            # FIX 2026-05-19: Block AI_BEARISH after 2 consecutive losses today (avoid 3× repeat)
            ai_losses_today = sum(1 for t in getattr(self, '_all_trades_ref', []) if t.module == self.name and t.pnl is not None and t.pnl < 0)
            if ai_losses_today >= 2:
                log.info(f"[AI] Pausing PE - {ai_losses_today} losses today, market not trending")
                return None
            c = self._best_contract(data, 'PE')
            if c:
                return Signal(self.name, "AI_BEARISH", "PE", c, bear_score,
                            f"AI score: bearish {bear_score:.2f}")
        return None
    
    def _best_contract(self, data: MarketData, side: str) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)

# ── Strategy 9: MEAN_REVERSION ─────────────────────────────────────────────
class MeanReversionModule(StrategyModule):
    """Strategy 9: Deviation fade with RSI confirmation"""
    def __init__(self):
        super().__init__("MEAN_REVERSION", "MEAN_REVERSION")
    
    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.day_open:
            return None
        
        dev = (data.spot - data.day_open) / data.day_open * 100
        
        # V3 TUNING: Use tighter threshold (0.35%) when RSI is extreme (>70 or <30)
        # Normal threshold: 0.5% = ~120 NIFTY points
        # Extreme RSI threshold: 0.35% = ~85 NIFTY points (catches earlier reversals)
        
        # Too far above open + RSI overbought → fade → BUY PE
        rsi = data.rsi14
        if not rsi:
            return None
        
        pe_threshold = 0.35 if rsi > 70 else 0.5
        ce_threshold = -0.35 if rsi < 30 else -0.5
        
        if dev > pe_threshold and rsi >= 65:
            c = self._best_contract(data, 'PE')
            if c:
                return Signal(self.name, "MEAN_REVERT_PE", "PE", c, 0.70,
                            f"Deviation {dev:.1f}% above open, RSI={rsi:.1f}")
        
        # Too far below open + RSI oversold → fade → BUY CE
        if dev < ce_threshold and rsi <= 35:
            c = self._best_contract(data, 'CE')
            if c:
                return Signal(self.name, "MEAN_REVERT_CE", "CE", c, 0.70,
                            f"Deviation {dev:.1f}% below open, RSI={rsi:.1f}")
        return None
    
    def _best_contract(self, data: MarketData, side: str) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)

# ── Strategy 10: SCALPING ──────────────────────────────────────────────────
class ScalpingModule(StrategyModule):
    """Strategy 10: Momentum scalp - 5 consecutive 1-min candles same direction
    + last candle move >= 2x average + PCR direction alignment.
    5 candles = 5 minutes of sustained momentum, not just random noise."""
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
        
        # Momentum: last candle move must be >= 2x the 20-candle average move
        moves = [abs(data.closes[i] - data.closes[i-1]) for i in range(-21, -1)]
        avg_move = sum(moves) / len(moves) if moves else 0
        last_move = abs(data.closes[-1] - data.closes[-2])
        strong_momentum = avg_move > 0 and last_move >= avg_move * 2.0
        
        # Total 5-candle move must be meaningful (>= 15 NIFTY points)
        total_move = abs(last5[-1] - last5[0])
        meaningful = total_move >= 15
        
        # V3 TUNING: Big-picture direction filter - don't scalp against strong intraday trend
        day_move = (data.spot - data.day_open) if data.day_open else 0
        
        if all_up and strong_momentum and meaningful:
            # PCR alignment: not bearish bias when going long
            if data.pcr_bias == 'BEARISH':
                return None
            # Block CE scalps if market already DOWN >30pts (was 80 - too loose)
            if day_move < -30:
                return None
            c = self._best_contract(data, 'CE', delta_min=0.35, delta_max=0.60)
            if c:
                return Signal(self.name, "SCALP_UP", "CE", c, 0.68,
                            f"5 up candles, move={total_move:.0f}pts, mom={last_move/avg_move:.1f}x")
        
        if all_down and strong_momentum and meaningful:
            # PCR alignment: not bullish bias when going short
            if data.pcr_bias == 'BULLISH':
                return None
            # Block PE scalps if market already UP >30pts (was 80 - too loose)
            if day_move > 30:
                return None
            c = self._best_contract(data, 'PE', delta_min=0.35, delta_max=0.60)
            if c:
                return Signal(self.name, "SCALP_DOWN", "PE", c, 0.68,
                            f"5 down candles, move={total_move:.0f}pts, mom={last_move/avg_move:.1f}x")
        return None
    
    def _best_contract(self, data: MarketData, side: str, delta_min=0.35, delta_max=0.60) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ── Strategy 11: BREAKOUT ─────────────────────────────────────────────────
class BreakoutModule(StrategyModule):
    """Strategy 11: 72-candle range breakout with retest confirmation.
    First breakout is noted. Entry only after price retests the breakout level."""
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
        
        # ── CE side: breakout + retest ──
        if not self.ce_fired:
            if not self._broke_ce:
                if spot > range_high * 1.002:
                    self._broke_ce = True
                    self._ce_level = range_high
                    log.info(f"[BREAKOUT] CE broke: spot={spot:.0f} > range_high={range_high:.0f}")
            elif not self._retest_ce:
                if spot <= self._ce_level * 1.002:
                    self._retest_ce = True
                    log.info(f"[BREAKOUT] CE retest: spot={spot:.0f} back to {self._ce_level:.0f}")
            else:
                if spot > self._ce_level * 1.002:
                    self.ce_fired = True
                    c = self._best_contract(data, 'CE', delta_min=0.40, delta_max=0.70)
                    if c:
                        return Signal(self.name, "BREAKOUT_CE", "CE", c, 0.78,
                                    f"Broke+retested {lookback}-candle high {self._ce_level:.0f}")
        
        # ── PE side: breakdown + retest ──
        if not self.pe_fired:
            if not self._broke_pe:
                if spot < range_low * 0.998:
                    self._broke_pe = True
                    self._pe_level = range_low
                    log.info(f"[BREAKOUT] PE broke: spot={spot:.0f} < range_low={range_low:.0f}")
            elif not self._retest_pe:
                if spot >= self._pe_level * 0.998:
                    self._retest_pe = True
                    log.info(f"[BREAKOUT] PE retest: spot={spot:.0f} back to {self._pe_level:.0f}")
            else:
                if spot < self._pe_level * 0.998:
                    self.pe_fired = True
                    c = self._best_contract(data, 'PE', delta_min=0.40, delta_max=0.70)
                    if c:
                        return Signal(self.name, "BREAKDOWN_PE", "PE", c, 0.78,
                                    f"Broke+retested {lookback}-candle low {self._pe_level:.0f}")
        return None
    
    def _best_contract(self, data: MarketData, side: str, delta_min=0.40, delta_max=0.70) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ── Strategy 12: VOLATILITY_BREAKOUT ───────────────────────────────────────
class VolatilityBreakoutModule(StrategyModule):
    """Strategy 12: High IV + EMA crossover.
    IV calculated from ATM ± 2 strikes only (not all OTM which dilute the signal)."""
    def __init__(self):
        super().__init__("VOLATILITY_BREAKOUT", "VOLATILITY_BREAKOUT")
    
    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.ema5 or not data.ema20:
            return None
        
        # Use ATM ± 2 strikes only for IV calculation (avoids deep OTM dilution)
        atm = data.atm_strike
        atm_strikes = [s for s in data.chain if abs(s - atm) <= 100]  # ±2 strikes of 50
        atm_contracts = [data.chain[s][side] for s in atm_strikes
                         for side in ('CE', 'PE') if side in data.chain[s]]
        if not atm_contracts:
            return None
        
        avg_iv = sum(c.iv for c in atm_contracts) / len(atm_contracts)
        if avg_iv < Config.IV_THRESHOLD:
            log.debug(f"[VOLBK] ATM IV {avg_iv:.1f}% below threshold {Config.IV_THRESHOLD}%")
            return None
        
        if data.ema5 > data.ema20 * 1.001:
            c = self._best_contract(data, 'CE')
            if c:
                return Signal(self.name, "VOL_BREAKOUT_CE", "CE", c, 0.70,
                            f"ATM IV {avg_iv:.1f}% + EMA5>EMA20")
        
        if data.ema5 < data.ema20 * 0.999:
            c = self._best_contract(data, 'PE')
            if c:
                return Signal(self.name, "VOL_BREAKOUT_PE", "PE", c, 0.70,
                            f"ATM IV {avg_iv:.1f}% + EMA5<EMA20")
        return None
    
    def _best_contract(self, data: MarketData, side: str) -> Optional[OptionContract]:
        chain = data.chain
        candidates = [chain[s][side] for s in chain
                      if side in chain[s] and Config.MIN_DELTA <= abs(chain[s][side].delta) <= Config.MAX_DELTA]
        if not candidates:
            return None
        max_vol = max(c.volume for c in candidates) or 1
        max_oi = max(c.oi for c in candidates) or 1
        return max(candidates, key=lambda c: abs(c.delta) * 0.4 + (c.volume / max_vol) * 0.3 + (c.oi / max_oi) * 0.3)

# ── Strategy 13: OPTIONS_GREEKS ───────────────────────────────────────────
class OptionsGreeksModule(StrategyModule):
    """Strategy 13: Delta-skew weighted by OI"""
    def __init__(self):
        super().__init__("OPTIONS_GREEKS", "OPTIONS_GREEKS")
        self._last_sl_time: Optional[datetime] = None
        self._fired_today = False  # FIX: max 1 entry per day - May 26: re-entered 3x same direction

    def reset_daily(self):
        super().reset_daily()
        self._last_sl_time = None
        self._fired_today = False

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if self._fired_today:  # FIX: one shot per day
            return None
        if self._last_sl_time and (datetime.now() - self._last_sl_time).total_seconds() < 1200:
            return None
        ce_skew = sum(abs(data.chain[s]['CE'].delta) * data.chain[s]['CE'].oi
                      for s in data.chain if 'CE' in data.chain[s])
        pe_skew = sum(abs(data.chain[s]['PE'].delta) * data.chain[s]['PE'].oi
                      for s in data.chain if 'PE' in data.chain[s])
        
        if ce_skew == 0 and pe_skew == 0:
            return None
        
        skew_ratio = ce_skew / (ce_skew + pe_skew)
        
        # CE signal: delta skew favours CE AND price is above EMA20 (trend confirmation)
        if skew_ratio > 0.55 and data.ema20 and data.spot > data.ema20:
            ces = [data.chain[s]['CE'] for s in data.chain 
                   if 'CE' in data.chain[s] and data.chain[s]['CE'].vega > 0]
            if not ces:
                return None
            c = max(ces, key=lambda x: x.vega * x.oi)
            if c.ltp <= Config.PREMIUM_MAX:
                self._fired_today = True
                return Signal(self.name, "GREEKS_CE", "CE", c, 0.70,
                            f"Delta skew {skew_ratio:.2f} CE bias + spot>EMA20")
        
        # PE signal: delta skew favours PE AND price is below EMA20 (trend confirmation)
        if skew_ratio < 0.45 and data.ema20 and data.spot < data.ema20:
            pes = [data.chain[s]['PE'] for s in data.chain 
                   if 'PE' in data.chain[s] and data.chain[s]['PE'].vega > 0]
            if not pes:
                return None
            c = max(pes, key=lambda x: x.vega * x.oi)
            if c.ltp <= Config.PREMIUM_MAX:
                self._fired_today = True
                return Signal(self.name, "GREEKS_PE", "PE", c, 0.70,
                            f"Delta skew {skew_ratio:.2f} PE bias + spot<EMA20")
        return None
    
    def _best_contract(self, data: MarketData, side: str, delta_min=0.45, delta_max=0.65) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ── Strategy 14: MAGIC_SQUARE ───────────────────────────────────────────────
class MagicSquareModule(StrategyModule):
    """Strategy 14: Magic Square - V4 dedup: strike+magic combo, max open limit, loss-blocked strikes"""
    def __init__(self):
        super().__init__("MAGIC_SQUARE", "MAGIC_SQUARE")
        self.opening_price = None
        self.traded_strikes: set = set()           # Strikes blocked (loss or active)
        self.traded_magic_numbers: set = set()     # Magic numbers already used
        self.strike_magic_combo: set = set()       # (strike, magic) combos used
    
    def analyze(self, data: MarketData) -> Optional[Signal]:
        # FIX June 2: Early exit if disabled (flat gap day or other reason)
        if not self.enabled:
            return None
        
        if self.opening_price is None and data.day_open:
            self.opening_price = data.day_open
            # FIX June 3: If prev_close missing (API fail), block Magic Square — cannot calculate gap
            if not data.prev_close:
                log.info("[MAGIC] No prev_close data available, disabling Magic Square for safety")
                self.enabled = False
                return None
            gap_pct = (data.day_open - data.prev_close) / data.prev_close * 100
            # V3 FIX: Block Magic Square on flat gap days (May 27+June 3: +0.00% gap, all entries lost)
            if abs(gap_pct) < 0.15:  # Flat day = no directional bias
                log.info(f"[MAGIC] Flat gap day ({gap_pct:+.2f}%), blocking Magic Square entries")
                self.enabled = False  # Disable for entire day
                return None
        
        # V3 FIX: Use Config.MAGIC_MAX_TRADES (now 2, was 5 - May 27: 5 entries all lost)
        if self.trade_count >= Config.MAGIC_MAX_TRADES:
            return None

        # P3: Tighter direction filter - spot vs open is primary signal
        # If market has moved >30pts from open in one direction, only trade that direction
        direction = 'BOTH'
        if self.opening_price:
            change = data.spot - self.opening_price
            if change > 30:       # Market up 30+ pts from open → CE only (was 40)
                direction = 'CE'
            elif change < -30:    # Market down 30+ pts from open → PE only (was 40)
                direction = 'PE'
        
        # PCR secondary filter only when direction is still ambiguous
        if direction == 'BOTH':
            if data.pcr_bias == 'BULLISH':
                direction = 'CE'
            elif data.pcr_bias == 'BEARISH':
                direction = 'PE'
        
        scan_types = ['CE', 'PE'] if direction == 'BOTH' else [direction]
        
        # Get sorted strikes and find ATM index
        all_strikes = sorted(data.chain.keys())
        if not all_strikes:
            return None
        
        atm_idx = 0
        for i, s in enumerate(all_strikes):
            if s >= data.atm_strike:
                atm_idx = i
                break
        
        # Scan ±10 strikes from ATM
        start_idx = max(0, atm_idx - 10)
        end_idx = min(len(all_strikes), atm_idx + 11)
        nearby_strikes = all_strikes[start_idx:end_idx]
        
        for opt_type in scan_types:
            valid_strikes = [s for s in nearby_strikes 
                           if opt_type in data.chain[s] and data.chain[s][opt_type].ltp < 500]
            
            for strike in valid_strikes:
                # V4 fix: skip if strike already used (loss or active)
                if strike in self.traded_strikes:
                    continue
                
                strike_data = data.chain[strike]
                opt = strike_data.get(opt_type)
                if not opt:
                    continue
                
                matched = self._find_magic_square(opt.ltp)
                if not matched:
                    continue
                
                # V4 fix: skip if (strike, magic) combo already used
                if (strike, matched) in self.strike_magic_combo:
                    continue
                
                delta_ok = Config.MAGIC_MIN_DELTA <= abs(opt.delta) <= Config.MAGIC_MAX_DELTA
                is_expiry_day = datetime.now().weekday() == 3
                theta_limit = 0.50 if is_expiry_day else 0.15
                theta_ok = abs(opt.theta) / opt.ltp < theta_limit if opt.ltp > 0 else True
                
                if delta_ok and theta_ok:
                    # Mark strike + combo immediately on signal (before entry confirmed)
                    self.traded_strikes.add(strike)
                    self.traded_magic_numbers.add(matched)
                    self.strike_magic_combo.add((strike, matched))
                    log.info(f"[MAGIC_SQUARE] Found {opt_type}{int(strike)} premium={opt.ltp:.2f} matches square {matched} (delta={opt.delta:.2f})")
                    return Signal(self.name, f"MAGIC_{matched}", opt_type, opt, 0.60,
                                f"Premium {opt.ltp:.0f} matches magic square {matched} at strike {int(strike)}")
        
        return None
    
    @staticmethod
    def _find_magic_square(premium: float) -> Optional[int]:
        for sq in Config.MAGIC_SQUARES:
            tolerance = max(sq * Config.MAGIC_TOLERANCE_PCT, 1.5)
            if abs(premium - sq) <= tolerance:
                return sq
        return None
    
    def reset_daily(self):
        """Reset all tracking on new day"""
        super().reset_daily()
        self.traded_strikes.clear()
        self.traded_magic_numbers.clear()
        self.strike_magic_combo.clear()

# ── Strategy 15: SHORT_UNWIND ──────────────────────────────────────────────
class ShortUnwindModule(StrategyModule):
    """Strategy 15: Put OI drop + spot rising"""
    def __init__(self):
        super().__init__("SHORT_UNWIND", "SHORT_UNWIND")
    
    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.prev_oi_state or data.prev_spot <= 0:
            return None
        if data.spot <= data.prev_spot:
            return None
        if not data.max_put_oi_strike:
            return None
        
        prev_pe_oi = data.prev_oi_state.get(data.max_put_oi_strike, {}).get('PE', 0)
        curr_pe_oi = data.chain.get(data.max_put_oi_strike, {}).get('PE', OptionContract(None, 0, 'PE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)).oi
        
        if prev_pe_oi <= 0:
            return None
        
        oi_drop = (prev_pe_oi - curr_pe_oi) / prev_pe_oi * 100
        if oi_drop < 10.0:
            return None
        
        log.info(f"SHORT_UNWIND: Put OI @ {data.max_put_oi_strike:.0f} dropped {oi_drop:.1f}% | spot {data.prev_spot:.0f}→{data.spot:.0f}")
        
        c = self._best_contract(data, 'CE')
        if c:
            return Signal(self.name, "SHORT_UNWIND", "CE", c, 0.80,
                        f"Put OI dropped {oi_drop:.1f}% at {data.max_put_oi_strike:.0f}")
        return None
    
    def _best_contract(self, data: MarketData, side: str) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)

# ── Strategy 16: LONG_UNWIND ──────────────────────────────────────────────
class LongUnwindModule(StrategyModule):
    """Strategy 16: Call OI drop + spot falling"""
    def __init__(self):
        super().__init__("LONG_UNWIND", "LONG_UNWIND")
    
    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.prev_oi_state or data.prev_spot <= 0:
            return None
        if data.spot >= data.prev_spot:
            return None
        if not data.max_call_oi_strike:
            return None
        
        prev_ce_oi = data.prev_oi_state.get(data.max_call_oi_strike, {}).get('CE', 0)
        curr_ce_oi = data.chain.get(data.max_call_oi_strike, {}).get('CE', OptionContract(None, 0, 'CE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)).oi
        
        if prev_ce_oi <= 0:
            return None
        
        oi_drop = (prev_ce_oi - curr_ce_oi) / prev_ce_oi * 100
        if oi_drop < 10.0:
            return None
        
        log.info(f"LONG_UNWIND: Call OI @ {data.max_call_oi_strike:.0f} dropped {oi_drop:.1f}% | spot {data.prev_spot:.0f}→{data.spot:.0f}")
        
        c = self._best_contract(data, 'PE')
        if c:
            return Signal(self.name, "LONG_UNWIND", "PE", c, 0.80,
                        f"Call OI dropped {oi_drop:.1f}% at {data.max_call_oi_strike:.0f}")
        return None
    
    def _best_contract(self, data: MarketData, side: str) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, Config.MIN_DELTA, Config.MAX_DELTA, max_premium=500)

# ── Strategy 17: WRITER_RESIST_BREAK ───────────────────────────────────────
class ResistBreakModule(StrategyModule):
    """Strategy 17: Above max call OI with 3-cycle confirmation"""
    def __init__(self):
        super().__init__("WRITER_RESIST_BREAK", "WRITER_RESIST_BREAK")
        self._wrb_consec = 0
    
    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.max_call_oi_strike:
            return None
        
        if data.spot <= data.max_call_oi_strike * 1.001:
            self._wrb_consec = 0
            return None
        
        if data.prev_oi_state:
            prev_ce_oi = data.prev_oi_state.get(data.max_call_oi_strike, {}).get('CE', 0)
            curr_ce_oi = data.chain.get(data.max_call_oi_strike, {}).get('CE', OptionContract(None, 0, 'CE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)).oi
            if prev_ce_oi > 0:
                oi_change = (prev_ce_oi - curr_ce_oi) / prev_ce_oi * 100
                if oi_change < 3.0:
                    self._wrb_consec = 0
                    return None
        
        self._wrb_consec += 1
        log.info(f"WRITER_RESIST_BREAK: Spot {data.spot:.0f} above call resistance {data.max_call_oi_strike:.0f} [{self._wrb_consec}/3]")
        
        if self._wrb_consec < 3:
            return None
        
        c = self._best_contract(data, 'CE', delta_min=0.40, delta_max=0.70)
        if c:
            return Signal(self.name, "RESIST_BREAK", "CE", c, 0.75,
                        f"Broke call resistance {data.max_call_oi_strike:.0f}")
        return None
    
    def _best_contract(self, data: MarketData, side: str, delta_min=0.40, delta_max=0.65) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ── Strategy 18: PUT_WRITER_SUPPORT ────────────────────────────────────────
class PutWriterSupportModule(StrategyModule):
    """Strategy 18: At max put OI with writers defending"""
    def __init__(self):
        super().__init__("PUT_WRITER_SUPPORT", "PUT_WRITER_SUPPORT")
    
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
        
        # Support-break invalidation: if spot has gone below the support level by > 10 pts
        # at any time this session, the support is broken — do not buy
        if data.day_low and data.day_low < data.max_put_oi_strike - 10:
            log.info(f"[PUT_SUPPORT] Invalidated: day_low={data.day_low:.0f} broke support {data.max_put_oi_strike:.0f}")
            return None
        
        oi_change_pct = 0
        if data.prev_oi_state:
            prev_pe_oi = data.prev_oi_state.get(data.max_put_oi_strike, {}).get('PE', 0)
            curr_pe_oi = data.chain.get(data.max_put_oi_strike, {}).get('PE', OptionContract(None, 0, 'PE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)).oi
            if prev_pe_oi > 0:
                oi_change_pct = (curr_pe_oi - prev_pe_oi) / prev_pe_oi * 100
                if curr_pe_oi < prev_pe_oi * 0.98:
                    return None
        
        log.info(f"PUT_WRITER_SUPPORT: Spot {data.spot:.0f} at put support {data.max_put_oi_strike:.0f} | writers defending (OI {oi_change_pct:+.1f}%) | {points_above:.0f}pt above")
        
        c = self._best_contract(data, 'CE')
        if c and c.strike <= data.spot + 100:
            return Signal(self.name, "PUT_SUPPORT", "CE", c, 0.70,
                        f"At put support {data.max_put_oi_strike:.0f}, {points_above:.0f}pt above")
        return None
    
    def _best_contract(self, data: MarketData, side: str, delta_min=0.45, delta_max=0.65) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ── Strategy 19: ORDER_BLOCK_REVERSAL ──────────────────────────────────────
class OrderBlockReversalModule(StrategyModule):
    """Strategy 19: Order block + support/resistance reversal.
    Based on user's manual method (May 18 2026):
    - Support = max PUT OI strike (put writers defending)
    - Resistance = max CALL OI strike (call writers capping)
    - Entry: price touches level + RSI confirms reversal + 3 candles confirm bounce/rejection
    - CE when price bounces off put support level (spot near max_put_OI and rising)
    - PE when price rejects from call resistance level (spot near max_call_OI and falling)
    """
    LEVEL_PROXIMITY_PCT = 0.005   # FIX 2026-05-19: 0.3%->0.5% (~115pts on 23700) at the level
    BOUNCE_CONFIRM_PCT  = 0.0008  # FIX 2026-05-19: 0.2%->0.08% (~19pts) to confirm bounce
    RSI_OVERSOLD        = 45      # FIX 2026-05-19: 40->45 (today RSI=33 at 23700 support, too strict)
    RSI_OVERBOUGHT      = 58      # FIX 2026-05-19: 60->58 (catches RSI=60 near resistance)

    def __init__(self):
        super().__init__("ORDER_BLOCK_REVERSAL", "ORD_BLOCK")
        self._touched_support   = False
        self._touched_resistance= False
        self._support_low       = None  # Lowest price seen while at support
        self._resistance_high   = None  # Highest price seen while at resistance

    def analyze(self, data: MarketData) -> Optional[Signal]:
        if not data.max_put_oi_strike or not data.max_call_oi_strike:
            return None
        if not data.rsi14:
            return None

        spot = data.spot
        support    = data.max_put_oi_strike
        resistance = data.max_call_oi_strike

        # ── CE: Bounce off PUT OI support ───────────────────────────────────
        dist_to_support = (spot - support) / support
        if dist_to_support <= self.LEVEL_PROXIMITY_PCT:
            # Price is AT or below support
            if not self._touched_support:
                self._touched_support = True
                self._support_low = spot
                log.info(f"[ORD_BLOCK] Touched PUT support {support:.0f} at spot={spot:.0f} RSI={data.rsi14:.0f}")
            else:
                # Track the lowest wick
                if spot < self._support_low:
                    self._support_low = spot
        elif self._touched_support and dist_to_support >= self.BOUNCE_CONFIRM_PCT:
            # Price has bounced away from support
            if data.rsi14 <= self.RSI_OVERSOLD:  # oversold + bouncing = CE
                self._touched_support = False
                self._support_low = None
                c = best_contract_premium_filtered(data, 'CE', delta_min=0.40, delta_max=0.65, max_premium=500)
                if c:
                    log.info(f"[ORD_BLOCK] CE signal: bounced off put support {support:.0f}, RSI={data.rsi14:.0f}")
                    return Signal(self.name, "SUPPORT_BOUNCE_CE", "CE", c, 0.78,
                                f"Bounced off OB support {support:.0f} RSI={data.rsi14:.0f}")
            # FIX 2026-05-19: Don't hard-reset if RSI slightly above threshold — keep tracking
            # (old code reset immediately if RSI>40, destroying the signal)
        elif not self._touched_support:
            pass  # Not near support, keep state clean

        # ── PE: Rejection at CALL OI resistance ─────────────────────────────
        dist_to_resist = (resistance - spot) / resistance
        if dist_to_resist <= self.LEVEL_PROXIMITY_PCT:
            # Price is AT or above resistance
            if not self._touched_resistance:
                self._touched_resistance = True
                self._resistance_high = spot
                log.info(f"[ORD_BLOCK] Touched CALL resistance {resistance:.0f} at spot={spot:.0f} RSI={data.rsi14:.0f}")
            else:
                if spot > self._resistance_high:
                    self._resistance_high = spot
        elif self._touched_resistance and dist_to_resist >= self.BOUNCE_CONFIRM_PCT:
            # Price has fallen away from resistance
            if data.rsi14 >= self.RSI_OVERBOUGHT:  # overbought + rejecting = PE
                self._touched_resistance = False
                self._resistance_high = None
                c = best_contract_premium_filtered(data, 'PE', delta_min=0.40, delta_max=0.65, max_premium=500)
                if c:
                    log.info(f"[ORD_BLOCK] PE signal: rejected from call resistance {resistance:.0f}, RSI={data.rsi14:.0f}")
                    return Signal(self.name, "RESISTANCE_REJECT_PE", "PE", c, 0.78,
                                f"Rejected at OB resistance {resistance:.0f} RSI={data.rsi14:.0f}")
            # FIX 2026-05-19: Don't reset immediately — keep tracking if RSI not yet confirming
        elif not self._touched_resistance:
            pass  # Not near resistance, keep state clean

        return None

    def _best_contract(self, data: MarketData, side: str, delta_min=0.40, delta_max=0.65) -> Optional[OptionContract]:
        return best_contract_premium_filtered(data, side, delta_min, delta_max, max_premium=500)

# ═════════════════════════════════════════════════════════════════════════════
# TRADE MANAGER
# ═════════════════════════════════════════════════════════════════════════════

class TradeManager:
    """Central trade manager - ₹50,000 per strategy"""
    
    def __init__(self):
        self.trades: List[Trade] = []
        self.same_dir_count = {'CE': 0, 'PE': 0}
        self.csv_file = f'daily_data/v3_trades_{today_str}.csv'
        self._init_csv()
        # FIX: Gap recovery state
        self._gap_down_day = False
        self._gap_recovered = False
        self._gap_recovery_logged = False
        self._market_open_time: Optional[datetime] = None
        # FIX 2026-05-19: Conflict suppression - track last win direction + time
        self._last_win_direction: Optional[str] = None
        self._last_win_time: Optional[datetime] = None
        self._conflict_suppress_mins = 20  # block opposite direction for 20 min after a win
    
    def _init_csv(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'event', 'trade_id', 'module', 'strategy',
                    'direction', 'strike', 'entry', 'exit', 'sl', 'target',
                    'pnl', 'exit_reason', 'confidence', 'reason', 'unreal_pnl'
                ])
    
    def _update_gap_recovery(self, data: MarketData):
        """FIX: Detect gap-down-and-reverse days, block new PE entries once recovered."""
        if not Config.GAP_RECOVERY_ENABLED or not data or not data.day_open or not data.prev_close:
            return
        now = datetime.now()
        if self._market_open_time is None:
            self._market_open_time = now
        mins_since_open = (now - self._market_open_time).seconds // 60
        if mins_since_open < Config.GAP_RECOVERY_AFTER_MINUTES:
            return
        gap_pct = (data.day_open - data.prev_close) / data.prev_close
        if gap_pct < -Config.GAP_RECOVERY_MIN_GAP_PCT:  # Real gap-down day (>0.5%)
            self._gap_down_day = True
        if self._gap_down_day:
            recovery_pct = (data.spot - data.day_open) / data.day_open
            if recovery_pct >= -Config.GAP_RECOVERY_THRESHOLD:  # Spot recovered to open
                if not self._gap_recovery_logged:
                    log.info(f"[GAP_RECOVERY] Gap-down day reversed: spot={data.spot:.0f} open={data.day_open:.0f} ({recovery_pct*100:+.2f}%) - blocking new PE entries")
                    self._gap_recovery_logged = True
                self._gap_recovered = True

    def can_enter(self, module: StrategyModule, direction: str, data: MarketData = None, signal_confidence: float = 0) -> bool:
        now = datetime.now()
        
        # V3 Adaptive Engine Regime Filtering
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

        # FIX 1: Portfolio-level circuit breaker - halt ALL entries if total loss too deep
        total_pnl = sum(t.pnl for t in self.trades if t.pnl is not None)
        if total_pnl <= Config.PORTFOLIO_LOSS_LIMIT:
            log.info(f"[CIRCUIT_BREAKER] Portfolio loss ₹{total_pnl:,.0f} <= limit ₹{Config.PORTFOLIO_LOSS_LIMIT:,} - halting ALL new entries")
            return False
        
        # FIX June 3: Strong intraday direction guard - block ALL strategies trading against trend
        # June 3: market bullish all day, 10 PE entries → -₹29K. This is the #1 killer.
        if data and data.day_open:
            intraday_move = data.spot - data.day_open
            if intraday_move > 50 and direction == 'PE':
                log.info(f"[DIRECTION_GUARD] Blocking PE for {module.name} - market UP {intraday_move:.0f}pts from open (strong bull)")
                return False
            if intraday_move < -50 and direction == 'CE':
                log.info(f"[DIRECTION_GUARD] Blocking CE for {module.name} - market DOWN {abs(intraday_move):.0f}pts from open (strong bear)")
                return False
        
        # FIX June 3: Global same-direction cap — max 3 open trades in same direction
        # June 3: 8+ PE trades open simultaneously, all stopped out when market reversed upward
        open_in_direction = sum(1 for t in self.trades 
                                if t.status == 'OPEN' and t.contract.option_type == direction)
        if open_in_direction >= 3:
            # June 4 LEARNING: Log reasoning for learning review
            open_trades_list = [f"{t.trade_id}({t.contract.option_type})" for t in self.trades if t.status == 'OPEN']
            log.info(f"[DIR_CAP] Blocking {module.name} {direction} - {open_in_direction}/3 open. Active: {open_trades_list}")
            return False

        # FIX 2026-05-19: Min premium guard — block deep OTM / decayed options
        if data and signal_confidence > 0:  # only when we have a real signal
            contract = getattr(getattr(module, 'open_trade', None), 'contract', None)
            # Check via data chain for current ATM premium
            atm_opt = data.chain.get(data.atm_strike, {}).get(direction)
            if atm_opt and atm_opt.ltp < Config.MIN_ENTRY_PREMIUM:
                log.info(f"[FILTER] Blocking {module.name} {direction} - ATM premium Rs.{atm_opt.ltp:.2f} < MIN Rs.{Config.MIN_ENTRY_PREMIUM}")
                return False

        # FIX 2026-05-19: Conflict suppression — only in morning (first 90min after open)
        # Afternoon sessions must run freely (RSI=88 at 11:51 was blocked by this — wrong)
        morning_cutoff_hour, morning_cutoff_min = Config.MARKET_OPEN[0], Config.MARKET_OPEN[1] + 90
        in_morning = (now.hour < morning_cutoff_hour + morning_cutoff_min // 60 or
                      (now.hour == morning_cutoff_hour + morning_cutoff_min // 60 and
                       now.minute < morning_cutoff_min % 60))
        if in_morning and self._last_win_direction and self._last_win_time:
            mins_since_win = (now - self._last_win_time).seconds // 60
            if mins_since_win < self._conflict_suppress_mins and direction != self._last_win_direction:
                log.info(f"[FILTER] Conflict suppression (morning only): last win was {self._last_win_direction} {mins_since_win}m ago — blocking {direction} for {module.name}")
                return False

        # FIX 2: Gap recovery block - no new PE if gap-down day has reversed
        if data:
            self._update_gap_recovery(data)
        if self._gap_recovered and direction == 'PE':
            log.info(f"[GAP_RECOVERY] Blocking PE for {module.name} - gap-down day has recovered")
            return False
        # Magic Square: Use Config.MAGIC_MAX_TRADES (was hardcoded 5 here — BUG fixed June 3)
        if module.name == 'MAGIC_SQUARE':
            if module.trade_count >= Config.MAGIC_MAX_TRADES:
                return False
            # FIX June 8: Max 1 simultaneous open (was unlimited - caused 6 open CEs on bearish day = -26K)
            ms_open = sum(1 for t in self.trades if t.module == 'MAGIC_SQUARE' and t.status == 'OPEN')
            if ms_open >= Config.MAGIC_MAX_OPEN_SIMULTANEOUS:
                log.info(f"[MAGIC_SQUARE] Blocking - already {ms_open} open position(s) (max {Config.MAGIC_MAX_OPEN_SIMULTANEOUS})")
                return False
        else:
            if module.trade_count >= Config.MAX_TRADES_PER_STRATEGY:
                return False
            if module.open_trade is not None:
                return False
        if module.net_pnl <= Config.DAILY_LOSS_LIMIT:
            return False
        # REMOVED: Same-direction blocking - each strategy trades independently
        # if self.same_dir_count[direction] >= Config.MAX_SAME_DIR_OPEN:
        #     return False
        
        # NEW: Gap-Day Override Check
        gap_override_active = False
        if Config.GAP_DAY_OVERRIDE_ENABLED and data and data.day_open and data.prev_close:
            gap_pts = data.day_open - data.prev_close
            mins_since_open = (now.hour - Config.MARKET_OPEN[0]) * 60 + (now.minute - Config.MARKET_OPEN[1])
            if mins_since_open <= Config.GAP_DAY_OVERRIDE_MINUTES:
                # Gap down day - allow PE trades regardless of PCR bias
                if gap_pts <= Config.GAP_DOWN_THRESHOLD and direction == 'PE':
                    log.info(f"[GAP OVERRIDE] Allowing PE trade for {module.name} - Gap down {gap_pts:.0f}pts (PCR bias ignored)")
                    gap_override_active = True
                # Gap up day - allow CE trades regardless of PCR bias
                if gap_pts >= Config.GAP_UP_THRESHOLD and direction == 'CE':
                    log.info(f"[GAP OVERRIDE] Allowing CE trade for {module.name} - Gap up {gap_pts:.0f}pts (PCR bias ignored)")
                    gap_override_active = True
        
        # NEW: Direction Filter - Block trades opposite to PCR bias (unless gap override active)
        if Config.DIRECTION_FILTER_ENABLED and data and signal_confidence >= Config.DIRECTION_FILTER_CONFIDENCE and not gap_override_active:
            if data.pcr_bias == 'BULLISH' and direction == 'PE':
                log.info(f"[FILTER] Blocking PE trade for {module.name} - PCR bias is BULLISH")
                return False
            if data.pcr_bias == 'BEARISH' and direction == 'CE':
                log.info(f"[FILTER] Blocking CE trade for {module.name} - PCR bias is BEARISH")
                return False
        
        # NEW: Price Momentum Filter - Block trades against strong price movement
        if Config.PRICE_MOMENTUM_ENABLED and data and data.day_open:
            price_change = data.spot - data.day_open
            if price_change > Config.PRICE_MOMENTUM_THRESHOLD and direction == 'PE':
                log.info(f"[FILTER] Blocking PE trade for {module.name} - Market UP {price_change:.0f} points (trending bullish)")
                return False
            if price_change < -Config.PRICE_MOMENTUM_THRESHOLD and direction == 'CE':
                log.info(f"[FILTER] Blocking CE trade for {module.name} - Market DOWN {abs(price_change):.0f} points (trending bearish)")
                return False
        
        # NEW: VWAP Chop Filter - Block entries when price is in choppy zone near VWAP
        if Config.VWAP_CHOP_FILTER_ENABLED and data and data.vwap and data.vwap > 0:
            vwap_dist_pct = abs(data.spot - data.vwap) / data.vwap
            if vwap_dist_pct < Config.VWAP_CHOP_BAND_PCT and module.name not in ('AI_ENHANCED',):  # FIX June 8: MAGIC_SQUARE now subject to VWAP chop filter
                log.info(f"[FILTER] Blocking {module.name} {direction} - Price near VWAP ({vwap_dist_pct*100:.2f}% away = choppy zone)")
                return False
        
        # NEW: Strike Diversification Check
        if data:
            strike_trades = sum(1 for t in self.trades 
                               if t.status == 'OPEN' and t.contract.strike == data.atm_strike)
            if strike_trades >= Config.MAX_TRADES_PER_STRIKE:
                log.info(f"[FILTER] Blocking trade - Max {Config.MAX_TRADES_PER_STRIKE} trades per strike reached")
                return False
        
        return True
    
    def has_open_trade(self, module: str) -> bool:
        for t in self.trades:
            if t.module == module and t.status == 'OPEN':
                return True
        return False
    
    def enter(self, signal: Signal, module: StrategyModule, data: MarketData = None) -> Optional[Trade]:
        if not self.can_enter(module, signal.direction, data, signal.confidence):
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
        
        # FIX June 9: High confidence boost (>0.90) for AI_ENHANCED
        high_confidence_boost = 1.0
        if signal.confidence >= 0.90 and module.name == 'AI_ENHANCED':
            high_confidence_boost = Config.HIGH_CONFIDENCE_SIZE_MULTIPLIER
            log.info(f"[SIZING] {module.name} HIGH CONFIDENCE {signal.confidence:.2f} → {high_confidence_boost:.0f}x size boost")
        
        adjusted_qty = int(Config.LOT_SIZE * size_multiplier * high_confidence_boost)
        
        trade = Trade(
            trade_id=f"{signal.module[:4]}_{datetime.now().strftime('%H%M%S')}",
            strategy=signal.strategy,
            module=signal.module,
            contract=signal.contract,
            entry_price=entry,
            quantity=adjusted_qty,
            target=round(entry * (1 + (Config.TARGET_PCT_HIGH_CONF if signal.confidence >= 0.90 else Config.TARGET_PCT)), 2),
            stop_loss=round(entry * (1 - Config.SL_PCT), 2),
            open_time=datetime.now()
        )
        
        self.trades.append(trade)
        # Magic Square: Allow multiple open trades - don't use singleton open_trade
        if module.name != 'MAGIC_SQUARE':
            module.open_trade = trade
        # Magic Square: Don't count on entry, count on exit (completed trades only)
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
    
    def update_unrealized_pnl(self, data: MarketData):
        for trade in self.trades:
            if trade.status != 'OPEN':
                continue
            strike_data = data.chain.get(trade.contract.strike, {})
            contract = strike_data.get(trade.contract.option_type)
            if contract:
                ltp = contract.ltp
                trade.unreal_pnl = (ltp - trade.entry_price) * trade.quantity
                trade.contract.ltp = ltp
    
    def manage_exits(self, data: MarketData, modules: Dict[str, StrategyModule]):
        for trade in self.trades:
            if trade.status != 'OPEN':
                continue
            
            strike_data = data.chain.get(trade.contract.strike, {})
            contract = strike_data.get(trade.contract.option_type)
            if not contract:
                continue
            
            ltp = contract.ltp
            ep = trade.entry_price
            
            if ep == 0:
                continue
            
            gain_pct = (ltp - ep) / ep
            trade.max_profit_pct = max(trade.max_profit_pct, gain_pct)
            
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
            elif (now.hour > Config.MARKET_CLOSE[0]) or (now.hour == Config.MARKET_CLOSE[0] and now.minute >= Config.MARKET_CLOSE[1]):
                close_reason = 'EOD'
            elif mins_open >= Config.TIME_STOP_MINUTES and loss_pct >= Config.TIME_STOP_LOSS_PCT:
                # V3 FIX: Skip TIME_STOP on gap days (>=50 pts) - give more room for reversals
                gap_pts = data.day_open - data.prev_close if data.day_open and data.prev_close else 0
                if abs(gap_pts) < 50:
                    close_reason = 'TIME_STOP'
                else:
                    log.info(f"[TIME_STOP BLOCKED] Trade {trade.trade_id} - Gap day ({gap_pts:+.0f}pts), giving more time")
            
            if close_reason:
                self._close_trade(trade, ltp, close_reason, contract, modules)
    
    def _close_trade(self, trade: Trade, exit_price: float, reason: str, 
                     contract: OptionContract, modules: Dict[str, StrategyModule]):
        trade.exit_price = exit_price
        trade.pnl = (exit_price - trade.entry_price) * trade.quantity
        trade.status = 'CLOSED'
        trade.close_time = datetime.now()
        trade.exit_reason = reason
        
        self.same_dir_count[trade.contract.option_type] -= 1
        
        module = modules.get(trade.module)
        if module:
            # Magic Square: Don't clear singleton (not used)
            if module.name != 'MAGIC_SQUARE':
                module.open_trade = None
            module.net_pnl += trade.pnl
            # Magic Square: Count completed trades on exit (not on entry)
            if module.name == 'MAGIC_SQUARE':
                module.trade_count += 1
                # Only release strike if it was a WIN - losing strikes stay blocked for the day
                if trade.pnl > 0:
                    if hasattr(module, 'traded_strikes') and trade.contract.strike in module.traded_strikes:
                        module.traded_strikes.remove(trade.contract.strike)
                        log.info(f"[MAGIC_SQUARE] Released strike {trade.contract.strike} (WIN - available for re-entry)")
                else:
                    log.info(f"[MAGIC_SQUARE] Strike {trade.contract.strike} BLOCKED for day (LOSS - no re-entry)")
        
        result = 'WIN' if trade.pnl > 0 else 'LOSS'
        
        # FIX 2026-05-19: Track last win for conflict suppression
        if trade.pnl > 0:
            self._last_win_direction = trade.contract.option_type
            self._last_win_time = datetime.now()

        # V3 FIX: OPTIONS_GREEKS 20min cooldown after SL (stop immediate re-entry)
        if reason == 'STOP_LOSS' and module and module.name == 'OPTIONS_GREEKS':
            if hasattr(module, '_last_sl_time'):
                module._last_sl_time = datetime.now()
                log.info(f"[OPTIONS_GREEKS] SL hit - 20min cooldown started")

        log.info(f"[EXIT] {trade.trade_id} | {result} | {reason} | "
                 f"Entry:₹{trade.entry_price:.2f} Exit:₹{exit_price:.2f} | "
                 f"P&L:₹{trade.pnl:+,.2f}")
        decision_logger.info(f"[EXIT] {trade.trade_id} | {result} | {reason} | P&L:₹{trade.pnl:+,.2f}")
        
        self._log_to_csv(trade, 'EXIT', None, reason)
    
    def _log_to_csv(self, trade: Trade, event: str, signal: Signal = None, exit_reason: str = ''):
        with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                event,
                trade.trade_id,
                trade.module,
                trade.strategy,
                trade.contract.option_type,
                int(trade.contract.strike),
                f"{trade.entry_price:.2f}",
                f"{trade.exit_price:.2f}" if trade.exit_price else '',
                f"{trade.stop_loss:.2f}",
                f"{trade.target:.2f}",
                f"{trade.pnl:.2f}" if trade.pnl else '',
                exit_reason,
                f"{signal.confidence:.2f}" if signal else '',
                signal.reason if signal else '',
                f"{trade.unreal_pnl:.2f}" if trade.unreal_pnl else '0.00'
            ])
    
    def get_total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades if t.status == 'CLOSED') + \
               sum(t.unreal_pnl for t in self.trades if t.status == 'OPEN')

# ═════════════════════════════════════════════════════════════════════════════
# MAIN TRADING ENGINE
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
# LIVE HEALTH MONITOR
# ═════════════════════════════════════════════════════════════════════════════

class LiveHealthMonitor:
    """
    Runs in a background thread every cycle.
    Qualifies, verifies and testifies the running program in ONE LINE per cycle.
    Compares what the audit found (expected) vs what is actually happening (live).
    """
    EXPECTED = {
        'ULTIMATE_DAY_HIGH_LOW':     {'fires_when': 'ORB15 break+retest',    'direction': 'BOTH', 'needs': '15 candles locked'},
        'DAY_HIGH_BEARISH':          {'fires_when': 'near day-high retest',   'direction': 'PE',   'needs': 'PCR>=1.1 RSI>=65'},
        'DAY_LOW_BULLISH':           {'fires_when': 'near day-low dbl-bot',   'direction': 'CE',   'needs': 'PCR>=1.2 RSI<=35'},
        'ENHANCED_BEARISH_REVERSAL': {'fires_when': 'near day-high RSI obuy', 'direction': 'PE',   'needs': 'RSI>=65 PCR>=0.9'},
        'ENHANCED_BULLISH_REVERSAL': {'fires_when': 'near day-low RSI osel',  'direction': 'CE',   'needs': 'PCR>=1.2 RSI<=35'},
        'DAY_HIGH_LOW_TRADITIONAL':  {'fires_when': '15min range break+ret',  'direction': 'BOTH', 'needs': '15 candles locked'},
        'TREND_FOLLOWING':           {'fires_when': 'gap-open continuation',  'direction': 'BOTH', 'needs': '0.2% gap from prevclose'},
        'AI_ENHANCED':               {'fires_when': 'ensemble score>=0.65',   'direction': 'BOTH', 'needs': 'RSI+PCR+MOM+EMA'},
        'MEAN_REVERSION':            {'fires_when': 'dev>=0.5% + RSI extreme','direction': 'BOTH', 'needs': 'RSI overbought/oversold'},
        'SCALPING':                  {'fires_when': '5 candles + 2x mom',     'direction': 'BOTH', 'needs': '15pt total move'},
        'BREAKOUT':                  {'fires_when': '72c range break+retest', 'direction': 'BOTH', 'needs': '73 candles available'},
        'VOLATILITY_BREAKOUT':       {'fires_when': 'ATM IV>=18 + EMA cross', 'direction': 'BOTH', 'needs': 'EMA5 vs EMA20'},
        'OPTIONS_GREEKS':            {'fires_when': 'skew>0.55 + EMA align',  'direction': 'BOTH', 'needs': 'spot vs EMA20'},
        'MAGIC_SQUARE':              {'fires_when': 'premium matches sq±5%',  'direction': 'BOTH', 'needs': 'delta ok + theta ok'},
        'SHORT_UNWIND':              {'fires_when': 'put OI drop + spot rise', 'direction': 'CE',  'needs': 'spot rising prev_oi'},
        'LONG_UNWIND':               {'fires_when': 'call OI drop + spot fall','direction': 'PE',  'needs': 'spot falling prev_oi'},
        'WRITER_RESIST_BREAK':       {'fires_when': 'spot>maxcallOI*1.001 3x','direction': 'CE',   'needs': '3 confirm cycles'},
        'PUT_WRITER_SUPPORT':        {'fires_when': 'spot near max put OI',   'direction': 'CE',   'needs': 'day_low>level-10'},
        'ORDER_BLOCK_REVERSAL':      {'fires_when': 'bounce/reject OI level',  'direction': 'BOTH', 'needs': 'RSI<40 at support or >60 at resist'},
    }

    def __init__(self, trader: 'ModularTrader'):
        self.trader = trader
        self._lock = threading.Lock()
        self._last_report: Dict[str, str] = {}
        self._cycle = 0

    def qualify(self, data: MarketData) -> None:
        """Called every trading cycle. Prints one-line live status per strategy."""
        self._cycle += 1
        now_str = datetime.now().strftime('%H:%M:%S')
        lines = []
        summary_flags = []

        spot = data.spot
        ema20 = data.ema20 or 0
        pcr = data.pcr
        rsi = data.rsi14 or 50
        dev = (spot - data.day_open) / data.day_open * 100 if data.day_open else 0
        atm = data.atm_strike
        is_expiry = datetime.now().weekday() == 3
        num_candles = len(data.closes)
        price_change = spot - (data.day_open or spot)

        tm = self.trader.trade_manager
        for mod in self.trader.modules:
            name = mod.name
            exp = self.EXPECTED.get(name, {})
            trade_count = mod.trade_count
            net_pnl = mod.net_pnl

            # Determine actual live status
            if name == 'MAGIC_SQUARE':
                # Magic Square: Check for multiple open trades
                ms_open = [t for t in tm.trades if t.module == 'MAGIC_SQUARE' and t.status == 'OPEN']
                if ms_open:
                    # Show count and first trade info
                    t = ms_open[0]
                    ltp = t.contract.ltp
                    ep  = t.entry_price
                    gain_pct = (ltp - ep) / ep * 100 if ep else 0
                    live_state = f"OPEN({len(ms_open)}) {t.contract.option_type}{int(t.contract.strike)} {gain_pct:+.1f}%"
                elif trade_count >= 10:
                    live_state = "MAX_REACHED"
                elif net_pnl <= Config.DAILY_LOSS_LIMIT:
                    live_state = "LOSS_LIMIT"
                else:
                    live_state = "WAITING"
            elif mod.open_trade:
                open_trade = mod.open_trade
                ltp = open_trade.contract.ltp
                ep  = open_trade.entry_price
                gain_pct = (ltp - ep) / ep * 100 if ep else 0
                live_state = f"OPEN {open_trade.contract.option_type}{int(open_trade.contract.strike)} {gain_pct:+.1f}%"
            elif trade_count >= Config.MAX_TRADES_PER_STRATEGY:
                live_state = "MAX_TRADES"
            elif net_pnl <= Config.DAILY_LOSS_LIMIT:
                live_state = "LOSS_LIMIT"
            else:
                live_state = "WAITING"

            # Qualification: can this strategy fire right now?
            qual_issues = []

            if name == 'ULTIMATE_DAY_HIGH_LOW':
                if mod.orb_high is None:
                    qual_issues.append(f"ORB not locked (need 15 candles, have {num_candles})")
                elif not mod._broke_ce and not mod._broke_pe:
                    qual_issues.append(f"ORB H={mod.orb_high:.0f} L={mod.orb_low:.0f} waiting breakout")
                elif mod._broke_ce and not mod._retest_ce:
                    qual_issues.append("CE broke, waiting retest")
                elif mod._broke_pe and not mod._retest_pe:
                    qual_issues.append("PE broke, waiting retest")
                else:
                    qual_issues.append("retest seen - watching for re-break")

            elif name == 'DAY_HIGH_BEARISH':
                if pcr < 1.1:   qual_issues.append(f"PCR={pcr:.2f}<1.1")
                if rsi < 65:    qual_issues.append(f"RSI={rsi:.0f}<65")
                if not qual_issues: qual_issues.append(f"READY spot={spot:.0f} ref_high={data.day_high:.0f}")

            elif name == 'DAY_LOW_BULLISH':
                if rsi <= 30:
                    qual_issues.append(f"RSI={rsi:.0f}<=30 (strong signal alone)")
                elif rsi <= 35 and pcr >= 0.9:
                    qual_issues.append(f"RSI={rsi:.0f}<=35 PCR={pcr:.2f}>=0.9")
                else:
                    if rsi > 35: qual_issues.append(f"RSI={rsi:.0f}>35")
                    if pcr < 0.9: qual_issues.append(f"PCR={pcr:.2f}<0.9")
                if not qual_issues: qual_issues.append(f"READY spot={spot:.0f} ref_low={data.day_low:.0f}")

            elif name == 'ENHANCED_BEARISH_REVERSAL':
                if rsi < 65:    qual_issues.append(f"RSI={rsi:.0f}<65")
                if pcr < 0.9:   qual_issues.append(f"PCR={pcr:.2f}<0.9")
                if not qual_issues: qual_issues.append(f"READY")

            elif name == 'ENHANCED_BULLISH_REVERSAL':
                if rsi <= 30:
                    qual_issues.append(f"RSI={rsi:.0f}<=30 (strong signal alone)")
                elif rsi <= 35 and pcr >= 0.9:
                    qual_issues.append(f"RSI={rsi:.0f}<=35 PCR={pcr:.2f}>=0.9")
                else:
                    if rsi > 35: qual_issues.append(f"RSI={rsi:.0f}>35")
                    if pcr < 0.9: qual_issues.append(f"PCR={pcr:.2f}<0.9")
                if not qual_issues: qual_issues.append(f"READY")

            elif name == 'DAY_HIGH_LOW_TRADITIONAL':
                if mod._range_high is None:
                    qual_issues.append(f"15min range not locked (have {num_candles} candles)")
                else:
                    qual_issues.append(f"H={mod._range_high:.0f} L={mod._range_low:.0f} broke_up={mod._broke_up} ret_up={mod._retest_up}")

            elif name == 'TREND_FOLLOWING':
                if not data.prev_close:
                    qual_issues.append("no prev_close")
                else:
                    gap = (data.day_open - data.prev_close) / data.prev_close * 100 if data.day_open else 0
                    qual_issues.append(f"gap={gap:+.2f}% (need ±0.2%)")

            elif name == 'AI_ENHANCED':
                qual_issues.append(f"RSI={rsi:.0f} PCR={pcr:.2f} bias={data.pcr_bias} EMA={'above' if spot>ema20 else 'below'}")

            elif name == 'MEAN_REVERSION':
                qual_issues.append(f"dev={dev:+.2f}% (need ±0.5%) RSI={rsi:.0f}")
                if abs(dev) < 0.5: qual_issues.append("dev too small")

            elif name == 'SCALPING':
                if num_candles < 5:
                    qual_issues.append(f"need 5 candles (have {num_candles})")
                else:
                    last5 = data.closes[-5:]
                    move = abs(last5[-1] - last5[0])
                    qual_issues.append(f"5c_move={move:.0f}pts (need 15)")

            elif name == 'BREAKOUT':
                lookback = Config.BREAKOUT_CANDLES
                if num_candles < lookback + 1:
                    qual_issues.append(f"need {lookback+1} candles (have {num_candles})")
                else:
                    rh = max(data.closes[-(lookback+1):-1])
                    rl = min(data.closes[-(lookback+1):-1])
                    qual_issues.append(f"range H={rh:.0f} L={rl:.0f} broke_ce={mod._broke_ce} ret_ce={mod._retest_ce}")

            elif name == 'VOLATILITY_BREAKOUT':
                atm_strikes = [s for s in data.chain if abs(s - atm) <= 100]
                ctrs = [data.chain[s][side] for s in atm_strikes for side in ('CE','PE') if side in data.chain[s]]
                avg_iv = sum(c.iv for c in ctrs)/len(ctrs) if ctrs else 0
                qual_issues.append(f"ATM_IV={avg_iv:.1f}% (need>={Config.IV_THRESHOLD}) EMA5={'>' if data.ema5 and data.ema20 and data.ema5>data.ema20 else '<'}EMA20")

            elif name == 'OPTIONS_GREEKS':
                ema_align = 'above' if spot > ema20 else 'below'
                qual_issues.append(f"spot {ema_align} EMA20 PCR={pcr:.2f} bias={data.pcr_bias}")

            elif name == 'MAGIC_SQUARE':
                theta_lim = 0.50 if is_expiry else 0.15
                qual_issues.append(f"expiry={is_expiry} theta_limit={theta_lim} scanning ATM±10 strikes")

            elif name in ('SHORT_UNWIND', 'LONG_UNWIND'):
                has_prev = bool(data.prev_oi_state)
                qual_issues.append(f"prev_oi={'YES' if has_prev else 'NO'} spot_rising={spot>(data.prev_spot or 0)}")

            elif name == 'WRITER_RESIST_BREAK':
                max_c = data.max_call_oi_strike or 0
                qual_issues.append(f"max_call_OI={max_c:.0f} spot={spot:.0f} need spot>{max_c*1.001:.0f}")

            elif name == 'PUT_WRITER_SUPPORT':
                max_p = data.max_put_oi_strike or 0
                broken = bool(data.day_low and data.day_low < max_p - 10)
                qual_issues.append(f"max_put_OI={max_p:.0f} broken={broken} day_low={data.day_low or 0:.0f}")

            elif name == 'ORDER_BLOCK_REVERSAL':
                support = data.max_put_oi_strike or 0
                resist  = data.max_call_oi_strike or 0
                dist_s  = (spot - support) / support * 100 if support else 0
                dist_r  = (resist - spot) / resist * 100 if resist else 0
                qual_issues.append(f"support={support:.0f} ({dist_s:+.2f}%) resist={resist:.0f} ({dist_r:+.2f}%) RSI={data.rsi14 or 0:.0f}")

            qual_str = '; '.join(qual_issues) if qual_issues else 'OK'

            # Build one-line status
            pnl_str = f"pnl={net_pnl:+.0f}"
            max_trades = 10 if name == 'MAGIC_SQUARE' else Config.MAX_TRADES_PER_STRATEGY
            trades_str = f"t={trade_count}/{max_trades}"
            line = (f"[HEALTH {now_str}] {name:<28} | {live_state:<28} | {trades_str} {pnl_str} | {qual_str}")
            lines.append(line)

            # Flag anything unexpected
            # Get open trade(s) for flagging
            if name == 'MAGIC_SQUARE':
                ms_open = [t for t in tm.trades if t.module == 'MAGIC_SQUARE' and t.status == 'OPEN']
                check_trade = ms_open[0] if ms_open else None
            else:
                check_trade = mod.open_trade
            
            if check_trade and net_pnl < -2000:
                summary_flags.append(f"{name} heavy loss {net_pnl:+.0f}")
            if check_trade:
                ltp = check_trade.contract.ltp
                ep  = check_trade.entry_price
                if ep > 0 and ltp <= 0.5:
                    summary_flags.append(f"{name} LTP near zero - check data feed!")

        # One-line console summary (not full table - that's display_table's job)
        # Count open trades: singleton for most, count from trades list for Magic Square
        open_count = 0
        for m in self.trader.modules:
            if m.name == 'MAGIC_SQUARE':
                open_count += len([t for t in tm.trades if t.module == 'MAGIC_SQUARE' and t.status == 'OPEN'])
            elif m.open_trade:
                open_count += 1
        total_pnl  = self.trader.trade_manager.get_total_pnl()
        ce_open    = self.trader.trade_manager.same_dir_count.get('CE', 0)
        pe_open    = self.trader.trade_manager.same_dir_count.get('PE', 0)
        flags_str  = ' !! ' + ' | '.join(summary_flags) if summary_flags else ''
        
        summary = (
            f"[HEALTH {now_str}] CYC#{self._cycle} "
            f"spot={spot:.0f} pcr={pcr:.3f}/{data.pcr_bias} rsi={rsi:.0f} dev={dev:+.2f}% "
            f"| OPEN:{open_count} CE:{ce_open} PE:{pe_open} "
            f"| P&L:Rs{total_pnl:+.0f} "
            f"| candles={num_candles}"
            f"{flags_str}"
        )
        log.info(summary)
        for line in lines:
            log.debug(line)

        # Write full strategy qualification to a separate health log every cycle
        health_log = log.getChild('health')
        for line in lines:
            health_log.info(line)


class ModularTrader:
    """Main engine V3 with table display, live health monitor - ALL 18 STRATEGIES"""
    
    def __init__(self):
        log.info("="*90)
        log.info("MODULAR TRADER V3 - ALL 18 STRATEGIES + LIVE HEALTH MONITOR")
        log.info("="*90)
        log.info("✅ REAL DHAN API ONLY - No simulation/fallback")
        log.info("✅ ₹50,000 capital per strategy (₹900,000 total)")
        log.info("✅ Comprehensive logging")
        log.info("✅ Best strategy: ULTIMATE_DAY_HIGH_LOW (ORB-45)")
        log.info("✅ Bonus: MAGIC_SQUARE strategy from V4")
        log.info("="*90)
        
        self.data_feed = DataFeed()
        self.health_monitor: Optional['LiveHealthMonitor'] = None
        
        # ALL 18 Strategy modules (17 original + Magic Square from V4)
        self.modules: List[StrategyModule] = [
            UltimateDayHighLowModule(),       # 1 - BEST PERFORMING
            DayHighBearishModule(),           # 2
            DayLowBullishModule(),            # 3
            DayLowBounceModule(),               # 3B - NEW June 4: Day low break + RSI<30
            EnhancedBearishModule(),          # 4
            EnhancedBullishModule(),          # 5
            DayHighLowTraditionalModule(),  # 6
            TrendFollowingModule(),           # 7
            AIEnhancedModule(),               # 8
            MeanReversionModule(),            # 9
            ScalpingModule(),                 # 10
            BreakoutModule(),                 # 11
            VolatilityBreakoutModule(),       # 12
            OptionsGreeksModule(),            # 13
            MagicSquareModule(),              # 14 - From V4
            ShortUnwindModule(),              # 15
            LongUnwindModule(),               # 16
            ResistBreakModule(),              # 17
            PutWriterSupportModule(),         # 18
            OrderBlockReversalModule(),       # 19 - User's manual method: OI support/resistance bounce
        ]
        
        self.module_dict = {m.name: m for m in self.modules}
        self.trade_manager = TradeManager()
        self.running = False
        self.cycle_count = 0
        # FIX 2026-05-19: Give AI module a reference to the shared trades list for loss counting
        for m in self.modules:
            if m.name == 'AI_ENHANCED':
                m._all_trades_ref = self.trade_manager.trades
                break
        
        # Reload open trades from CSV so SL/target management survives restarts
        self._reload_open_trades_from_csv()
        
        log.info(f"[INIT] {len(self.modules)} strategy modules loaded")
        for i, m in enumerate(self.modules, 1):
            log.info(f"[INIT]   {i:2d}. {m.display_name}")
        log.info(f"[INIT] Capital: {len(self.modules)} × ₹{Config.CAPITAL_PER_STRATEGY:,} = ₹{len(self.modules) * Config.CAPITAL_PER_STRATEGY:,}")
        log.info(f"[INIT] Lot size: {Config.LOT_SIZE}")
        log.info("="*90)
        
        # Attach health monitor
        self.health_monitor = LiveHealthMonitor(self)
    
    def is_market_hours(self) -> bool:
        now = datetime.now()
        hour, minute = now.hour, now.minute
        if hour < Config.MARKET_OPEN[0] or (hour == Config.MARKET_OPEN[0] and minute < Config.MARKET_OPEN[1]):
            return False
        if hour > Config.MARKET_CLOSE[0] or (hour == Config.MARKET_CLOSE[0] and minute >= Config.MARKET_CLOSE[1]):
            return False
        return True
    
    def display_table(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        
        data = self.data_feed.get_current_data()
        tm = self.trade_manager
        
        tm.update_unrealized_pnl(data)
        
        # Get ATM premium range from chain
        atm_ce = data.chain.get(data.atm_strike, {}).get('CE')
        atm_pe = data.chain.get(data.atm_strike, {}).get('PE')
        atm_ce_premium = atm_ce.ltp if atm_ce else 0
        atm_pe_premium = atm_pe.ltp if atm_pe else 0
        
        print("="*90)
        print(f" CYCLE {self.cycle_count} | {datetime.now().strftime('%H:%M:%S')} | "
              f"NIFTY {data.spot:.2f} | O:{data.day_open or 0:.1f} H:{data.day_high or 0:.1f} L:{data.day_low or 0:.1f} | "
              f"PCR:{data.pcr:.3f} | BIAS:{data.pcr_bias}")
        print(f" ATM:{int(data.atm_strike)} CE:{atm_ce_premium:.2f} PE:{atm_pe_premium:.2f} | Data:{'OK' if data.chain else 'NO CHAIN'}")
        print("="*90)
        
        print(f"\n {'#':<3} {'STRATEGY':<26} {'STATUS':<10} {'CONTRACT':<12} {'ENTRY':>8} {'LTP':>8} {'UNREAL P&L':>12} {'NET P&L':>12} {'TRADES':>7}")
        print("-"*90)
        
        total_net_pnl = 0.0
        total_unreal = 0.0
        total_trades = 0
        
        for idx, m in enumerate(self.modules, 1):
            # For Magic Square: get all open trades from trades list (not singleton)
            if m.name == 'MAGIC_SQUARE':
                open_trades = [t for t in tm.trades if t.module == 'MAGIC_SQUARE' and t.status == 'OPEN']
                if open_trades:
                    for t in open_trades:
                        strike = int(t.contract.strike)
                        opt_type = t.contract.option_type
                        entry = t.entry_price
                        ltp = t.contract.ltp
                        unreal = t.unreal_pnl
                        net = m.net_pnl
                        count = m.trade_count
                        
                        total_unreal += unreal
                        total_net_pnl += net
                        total_trades += 1
                        
                        contract_str = f"{opt_type}{strike}"
                        status = "OPEN"
                        
                        print(f" {idx:<3} {m.display_name:<26} {status:<10} {contract_str:<12} {entry:>8.2f} {ltp:>8.2f} {unreal:>+11.2f} {net:>+11.2f} {count:>7}")
                else:
                    status = "WAITING"
                    if m.trade_count >= 10:
                        status = "MAX_REACHED"
                    elif m.net_pnl <= Config.DAILY_LOSS_LIMIT:
                        status = "LOSS_LIMIT"
                    
                    net = m.net_pnl
                    total_net_pnl += net
                    total_trades += m.trade_count
                    
                    print(f" {idx:<3} {m.display_name:<26} {status:<10} {'-':<12} {'-':>8} {'-':>8} {'-':>12} {net:>+11.2f} {m.trade_count:>7}")
            elif m.open_trade:
                t = m.open_trade
                strike = int(t.contract.strike)
                opt_type = t.contract.option_type
                entry = t.entry_price
                ltp = t.contract.ltp
                unreal = t.unreal_pnl
                net = m.net_pnl
                count = m.trade_count
                
                total_unreal += unreal
                total_net_pnl += net
                total_trades += count
                
                contract_str = f"{opt_type}{strike}"
                status = "OPEN"
                
                print(f" {idx:<3} {m.display_name:<26} {status:<10} {contract_str:<12} {entry:>8.2f} {ltp:>8.2f} {unreal:>+11.2f} {net:>+11.2f} {count:>7}")
            else:
                status = "WAITING"
                if m.trade_count >= Config.MAX_TRADES_PER_STRATEGY:
                    status = "MAX_REACHED"
                elif m.net_pnl <= Config.DAILY_LOSS_LIMIT:
                    status = "LOSS_LIMIT"
                
                net = m.net_pnl
                total_net_pnl += net
                total_trades += m.trade_count
                
                print(f" {idx:<3} {m.display_name:<26} {status:<10} {'-':<12} {'-':>8} {'-':>8} {'-':>12} {net:>+11.2f} {m.trade_count:>7}")
        
        print("-"*90)
        
        total_capital = len(self.modules) * Config.CAPITAL_PER_STRATEGY
        print(f" TOTAL NET P&L: ₹{total_net_pnl:+,.2f} | Unrealized: ₹{total_unreal:+,.2f} | Trades: {total_trades}")
        print(f" CAPITAL: {len(self.modules)} × ₹{Config.CAPITAL_PER_STRATEGY:,} = ₹{total_capital:,}")
        
        daily_usage = abs(total_net_pnl) / abs(Config.DAILY_LOSS_LIMIT * len(self.modules)) if Config.DAILY_LOSS_LIMIT != 0 else 0
        bar_filled = int(min(daily_usage * 20, 20))
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        print(f" DAILY LIMIT: ₹{Config.DAILY_LOSS_LIMIT * len(self.modules):,.0f} | Used: ₹{total_net_pnl:,.0f} ({daily_usage*100:.1f}%) [{bar}]")
        
        print(f"\n CE Open: {tm.same_dir_count['CE']} | PE Open: {tm.same_dir_count['PE']} | UNLIMITED")
        
        print("="*90)
        print(" Press Ctrl+C to stop")
        print("="*90)
    
    def _reload_open_trades_from_csv(self):
        """On startup: read CSV, find truly-open ENTER rows, rebuild Trade objects.
        This ensures SL/target management continues after a program restart."""
        csv_file = self.trade_manager.csv_file
        if not os.path.exists(csv_file):
            return
        enters = {}
        exited_ids = set()
        try:
            with open(csv_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('event') == 'ENTER':
                        enters[row['trade_id']] = row
                    elif row.get('event') == 'EXIT':
                        exited_ids.add(row['trade_id'])
        except Exception as e:
            log.warning(f"[RELOAD] Could not read CSV: {e}")
            return
        
        open_rows = [r for tid, r in enters.items() if tid not in exited_ids]
        
        # Populate Magic Square traded_strikes from ALL trades (both open and closed)
        # so we don't trade same strike twice even after restart
        ms_mod = self.module_dict.get('MAGIC_SQUARE')
        if ms_mod and isinstance(ms_mod, MagicSquareModule):
            for row in enters.values():
                if row.get('module') == 'MAGIC_SQUARE':
                    try:
                        strike = float(row['strike'])
                        ms_mod.traded_strikes.add(strike)
                    except:
                        pass
            if ms_mod.traded_strikes:
                log.info(f"[RELOAD] Magic Square: Loaded {len(ms_mod.traded_strikes)} traded strikes from CSV: {sorted(ms_mod.traded_strikes)}")
        
        if not open_rows:
            log.info("[RELOAD] No open trades to reload")
            return
        
        log.info(f"[RELOAD] Found {len(open_rows)} open trades from previous session - reloading")
        for row in open_rows:
            try:
                strike = int(float(row['strike']))
                direction = row['direction']
                entry_price = float(row['entry'])
                sl = float(row['sl'])
                tgt = float(row['target'])
                opt_type = direction
                contract = OptionContract(
                    security_id=None, strike=strike, option_type=opt_type,
                    ltp=entry_price, ask=0, bid=0,
                    delta=0.5, gamma=0, theta=0, vega=0, iv=0, oi=0, volume=0
                )
                trade = Trade(
                    trade_id=row['trade_id'],
                    strategy=row['strategy'],
                    module=row['module'],
                    contract=contract,
                    entry_price=entry_price,
                    quantity=Config.LOT_SIZE,
                    target=tgt,
                    stop_loss=sl,
                    open_time=datetime.now()
                )
                self.trade_manager.trades.append(trade)
                # Reconnect to module
                mod = self.module_dict.get(row['module'])
                if mod:
                    # Magic Square: Don't use singleton, don't count on reload (count on exit only)
                    if mod.name != 'MAGIC_SQUARE' and mod.open_trade is None:
                        mod.open_trade = trade
                    # Only increment trade_count for non-Magic Square on reload
                    if mod.name != 'MAGIC_SQUARE':
                        mod.trade_count += 1
                self.trade_manager.same_dir_count[direction] += 1
                log.info(f"[RELOAD] Restored {row['trade_id']} | {direction}{strike} entry={entry_price} sl={sl} tgt={tgt}")
            except Exception as e:
                log.warning(f"[RELOAD] Could not restore trade {row.get('trade_id','?')}: {e}")

    def _signal_cycle(self, data: MarketData):
        """
        Inner fast cycle: analyze all strategies + fire orders.
        Called every 10s from the fast loop.
        Does NOT update data itself - data is passed in from the latest refresh.
        """
        self.cycle_count += 1

        self.trade_manager.manage_exits(data, self.module_dict)

        # Health monitor
        if self.health_monitor:
            try:
                self.health_monitor.qualify(data)
            except Exception as e:
                log.warning(f"[HEALTH] Monitor error: {e}")

        all_signals = []
        for module in self.modules:
            if not module.enabled:
                continue
            try:
                signal = module.analyze(data)
                if signal:
                    log.info(f"[SIGNAL] {module.display_name}: {signal.strategy} {signal.direction} "
                             f"(conf: {signal.confidence:.0%}) - {signal.reason}")
                    all_signals.append((signal, module))
            except Exception as e:
                log.error(f"[MODULE ERROR] {module.name}: {e}")

        all_signals.sort(key=lambda x: x[0].confidence, reverse=True)
        # FIX 2026-05-19: Allow max 1 CE + 1 PE per cycle (prevents 3×PE cluster at open)
        # But still take the single best signal per direction
        entered_dirs: set = set()
        for signal, module in all_signals:
            if signal.direction in entered_dirs:
                continue  # already took a trade in this direction this cycle
            if not self.trade_manager.can_enter(module, signal.direction, data, signal.confidence):
                continue
            self.trade_manager.enter(signal, module, data)
            entered_dirs.add(signal.direction)
            if len(entered_dirs) >= 2:  # max 1 CE + 1 PE per cycle
                break

    def run_cycle(self):
        """Legacy single-cycle (used by tests). In live use, run() uses the dual-loop."""
        self.cycle_count += 1
        self.data_feed.update()
        data = self.data_feed.get_current_data()
        self.trade_manager.manage_exits(data, self.module_dict)
        if self.health_monitor:
            try:
                self.health_monitor.qualify(data)
            except Exception as e:
                log.warning(f"[HEALTH] Monitor error: {e}")
        all_signals = []
        for module in self.modules:
            if not module.enabled:
                continue
            try:
                signal = module.analyze(data)
                if signal:
                    log.info(f"[SIGNAL] {module.display_name}: {signal.strategy} {signal.direction} "
                             f"(conf: {signal.confidence:.0%}) - {signal.reason}")
                    all_signals.append((signal, module))
            except Exception as e:
                log.error(f"[MODULE ERROR] {module.name}: {e}")
        all_signals.sort(key=lambda x: x[0].confidence, reverse=True)
        for signal, module in all_signals:
            if not self.trade_manager.can_enter(module, signal.direction, data, signal.confidence):
                continue
            self.trade_manager.enter(signal, module, data)
            break
    
    def run(self):
        """
        DUAL-LOOP ARCHITECTURE:
          FAST LOOP  (every 10s): spot refresh + strategy analysis + order fire
          SLOW LOOP  (every 30s): full chain+OI refresh + terminal display

        Timeline per 30s window:
          T+0s  : full update (chain+OI) + display_table
          T+10s : fast_update (spot only) + _signal_cycle  ← orders can fire here
          T+20s : fast_update (spot only) + _signal_cycle  ← orders can fire here
          T+30s : full update (chain+OI) + display_table   ← repeat
        """
        log.info("[RUN] Starting main loop - 18 STRATEGIES ACTIVE (V3) | DUAL-LOOP 10s/30s")
        decision_logger.info("[SESSION START] Modular Trader V3 - 18 Strategies + LiveHealthMonitor")
        self.running = True
        
        FAST_INTERVAL  = 10   # seconds between signal evaluations
        SLOW_INTERVAL  = 30   # seconds between full chain refresh + display
        
        last_full_update = 0.0  # epoch time of last full update
        
        try:
            while self.running:
                if not self.is_market_hours():
                    log.info("[RUN] Market closed - stopping")
                    self._force_eod_exit_for_all()
                    break

                try:
                    now = time.monotonic()

                    if now - last_full_update >= SLOW_INTERVAL:
                        # ── SLOW PATH: full chain + OI refresh + display ──────────
                        self.data_feed.update()           # ~3-4s (chain+OI+prev_close+VIX)
                        last_full_update = time.monotonic()
                        self.display_table()               # terminal refresh
                        data = self.data_feed.get_current_data()
                        self._signal_cycle(data)           # also run signals after full update
                    else:
                        # ── FAST PATH: spot + LTP refresh + signals ───────────────
                        ok = self.data_feed.fast_update()  # ~0.5s (spot/closes only)
                        if ok:
                            data = self.data_feed.get_current_data()
                            self._signal_cycle(data)
                        else:
                            log.warning("[RUN] fast_update failed - skipping signal cycle")

                    time.sleep(FAST_INTERVAL)

                except Exception as e:
                    import traceback
                    log.error(f"[RUN] Cycle error (will retry in 15s): {e}")
                    log.error(traceback.format_exc())
                    time.sleep(15)   # back-off then continue - session never stops on errors

        except KeyboardInterrupt:
            log.info("[RUN] User stopped")
            self._force_eod_exit_for_all()
        finally:
            self.running = False
            tm = self.trade_manager
            final_pnl = tm.get_total_pnl()
            closed = [t for t in tm.trades if t.status == 'CLOSED']
            wins   = [t for t in closed if t.pnl and t.pnl > 0]
            losses = [t for t in closed if t.pnl and t.pnl <= 0]
            log.info("="*90)
            log.info("TRADING SESSION COMPLETE (V3)")
            log.info(f"Total Trades: {len(closed)}")
            log.info(f"Final P&L: \u20b9{final_pnl:+,.2f}")
            log.info(f"CSV Log: {tm.csv_file}")
            log.info("="*90)
            decision_logger.info(f"[SESSION END] Final P&L: \u20b9{final_pnl:+,.2f}")

            # ── END-OF-DAY TERMINAL SUMMARY (visible in the CMD window) ──────
            LINE = "=" * 70
            pnl_str = f"Rs.{final_pnl:+,.2f}"
            emoji   = "PROFIT" if final_pnl >= 0 else "LOSS"
            print("\n" + LINE)
            print(f"  MODULAR TRADER V3  |  SESSION COMPLETE  |  {datetime.now().strftime('%d-%b-%Y')}")
            print(LINE)
            print(f"  Final P&L   : {pnl_str}  [{emoji}]")
            print(f"  Total Trades: {len(closed)}   |   Wins: {len(wins)}   |   Losses: {len(losses)}")
            if closed:
                win_rate = len(wins) / len(closed) * 100
                print(f"  Win Rate    : {win_rate:.0f}%")
            print(LINE)
            print("  STRATEGY BREAKDOWN:")
            print(f"  {'Strategy':<28} {'Trades':>6}  {'Net P&L':>12}")
            print("  " + "-"*50)
            for mod in self.modules:
                if mod.trade_count > 0 or mod.net_pnl != 0:
                    print(f"  {mod.name:<28} {mod.trade_count:>6}  Rs.{mod.net_pnl:>+10,.2f}")
            print(LINE)
            print(f"  Log files in: daily_data/")
            print(f"  CSV : {tm.csv_file}")
            print(LINE + "\n")

    def _force_eod_exit_for_all(self):
        """Force EOD exit for ALL open trades including from previous sessions"""
        log.info("[EOD] Forcing exit for all open trades...")
        
        # Load all trades from CSV - only truly open ones (no matching EXIT row)
        all_trades = []
        if os.path.exists(self.trade_manager.csv_file):
            enters = {}
            exited_ids = set()
            with open(self.trade_manager.csv_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('event') == 'ENTER':
                        enters[row['trade_id']] = row
                    elif row.get('event') == 'EXIT':
                        exited_ids.add(row['trade_id'])
            # Only include trades that have no EXIT row
            all_trades = [row for tid, row in enters.items() if tid not in exited_ids]
        
        if all_trades:
            log.info(f"[EOD] Found {len(all_trades)} orphaned open trades from CSV")
            # Get current market data for LTP
            try:
                data = self.data_feed.get_current_data()
                for trade_row in all_trades:
                    strike = int(float(trade_row['strike']))
                    direction = trade_row['direction']
                    entry = float(trade_row['entry'])
                    
                    # Get current LTP
                    strike_data = data.chain.get(strike, {})
                    contract = strike_data.get(direction)
                    ltp = contract.ltp if contract else entry * 0.5  # Fallback
                    
                    # Calculate P&L
                    qty = Config.LOT_SIZE
                    pnl = (ltp - entry) * qty
                    
                    # Log the forced exit
                    log.info(f"[EOD EXIT] {trade_row['trade_id']} | {direction}{strike} | Entry:₹{entry:.2f} | Exit:₹{ltp:.2f} | P&L:₹{pnl:+.2f}")
                    
                    # Update CSV with exit
                    with open(self.trade_manager.csv_file, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'EXIT', trade_row['trade_id'], trade_row['module'], trade_row['strategy'],
                            direction, strike, entry, f"{ltp:.2f}", '', '',
                            f"{pnl:.2f}", 'EOD_FORCE', trade_row['confidence'], trade_row['reason'], '0.00'
                        ])
                log.info(f"[EOD] All {len(all_trades)} orphaned trades marked as exited")
            except Exception as e:
                log.error(f"[EOD] Error forcing exits: {e}")
        else:
            log.info("[EOD] No orphaned trades found")

def main():
    try:
        trader = ModularTrader()
        trader.run()
    except Exception as e:
        log.error(f"[MAIN] Failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
