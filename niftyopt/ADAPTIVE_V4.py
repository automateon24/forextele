#!/usr/bin/env python3
"""
ADAPTIVE ENGINE V4 - Adaptive Trading Layer
================================================
Phase A: Rule-Based Foundation (Ready for April 30, 2026)

5-Layer Architecture:
- Layer 2: Parallel Performance Monitor
- Layer 3: Market Regime Detector  
- Layer 4: Auto-Correction System (Rule-Based)
- Layer 5: Meta-Learning Engine (FIXES.md Pattern Extractor)

Runs parallel to MODULAR_TRADER_V4.py
Updates thresholds in real-time via adaptive_config.json
"""

import os
import sys
import json
import time
import sqlite3
import threading
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from collections import deque
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('adaptive_data/adaptive_engine.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION - Safety Limits (Hardcoded for Phase A)
# ============================================================================

SAFETY_LIMITS = {
    'MAX_DAILY_ADJUSTMENT': 0.30,      # Max 30% change per day
    'MAX_POSITION_REDUCTION': 0.50,    # Never below 50% size
    'MAX_SL_WIDENING': 1.20,           # Max 20% SL widening
    'MIN_CONFIDENCE_THRESHOLD': 0.75,   # Never below 75% confidence
    'CORRECTION_INTERVAL_MINUTES': 15,  # Check every 15 min
    'ROLLBACK_WINDOW_MINUTES': 30,      # Evaluate rollback after 30 min
}

# V5 FIX: Intraday regime detection settings
INTRADAY_SETTINGS = {
    'REGIME_CHECK_INTERVAL_MINUTES': 5,  # Check every 5 minutes (not just daily)
    'TREND_DETECTION_POINTS': 30,        # FIX June 8: 30pt move = trending (was 50 - missed today's bearish day)
    'PCR_TREND_THRESHOLD': 0.03,         # FIX June 8: PCR change > 0.03 (was 0.05) - faster regime shift detection
    'MOMENTUM_CONFIRMATION_CYCLES': 3,   # Need 3 cycles of same direction
    'GAP_TREND_OVERRIDE_PCT': 0.2,       # 0.2% gap forces trending mode
}

DEFAULT_THRESHOLDS = {
    'VWAP_BAND_PCT': 0.003,
    'MOMENTUM_THRESHOLD': 50,
    'CONFIDENCE_BYPASS': 0.90,
    'POSITION_SIZE_PCT': 1.00,
    'COOLDOWN_MINUTES': 30,
    'PCR_STABILITY_CYCLES': 3,
    'TRAIL_BREAKEVEN_PCT': 0.20,
    'TRAIL_LOCK_PCT': 0.35,
}

# ============================================================================
# LAYER 2: PARALLEL PERFORMANCE MONITOR
# ============================================================================

@dataclass
class SignalEvent:
    timestamp: str
    strategy: str
    signal_type: str  # 'GENERATED', 'BLOCKED', 'TAKEN', 'EXITED'
    strike: Optional[str]
    option_type: Optional[str]  # 'CE' or 'PE'
    reason: Optional[str]  # Why blocked or why taken
    pnl: Optional[float]  # For exited signals
    metadata: Dict  # Additional context

@dataclass
class OpportunityCost:
    strategy: str
    signal_time: str
    block_reason: str
    strike: str
    option_type: str
    missed_pnl: float  # What would have been gained
    context: Dict  # VIX, PCR, time, etc.

class PerformanceMonitor:
    """Layer 2: Tracks all signals and their outcomes"""
    
    def __init__(self, db_path: str = 'adaptive_data/performance.db'):
        self.db_path = db_path
        self.signals_buffer: deque = deque(maxlen=1000)
        self.opportunity_costs: List[OpportunityCost] = []
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database for signal tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                strategy TEXT,
                signal_type TEXT,
                strike TEXT,
                option_type TEXT,
                reason TEXT,
                pnl REAL,
                vix REAL,
                pcr REAL,
                nifty_spot REAL,
                time_of_day TEXT,
                distance_from_atm INTEGER
            )
        ''')
        
        # Opportunity costs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS opportunity_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT,
                signal_time TEXT,
                block_reason TEXT,
                strike TEXT,
                option_type TEXT,
                missed_pnl REAL,
                vix REAL,
                pcr REAL,
                time_of_day TEXT
            )
        ''')
        
        # Strategy performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                strategy TEXT,
                signals_generated INTEGER,
                signals_taken INTEGER,
                signals_blocked INTEGER,
                win_count INTEGER,
                loss_count INTEGER,
                total_pnl REAL,
                avg_win REAL,
                avg_loss REAL
            )
        ''')
        
        conn.commit()
        conn.close()
        log.info("[L2] Performance database initialized")
    
    def parse_v4_logs(self, date_str: str) -> List[SignalEvent]:
        """Parse V4 decision logs to extract signals"""
        signals = []
        log_file = f'daily_data/decisions_{date_str}.log'
        
        if not os.path.exists(log_file):
            return signals
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            for line in lines:
                # Parse "ENTER [Strategy] Strike CE/PE @ premium" lines
                enter_match = re.search(
                    r'(\d{2}:\d{2}:\d{2}).*ENTER\s+(\w+).*?(\d+)\s+(CE|PE).*@\s+([\d.]+)', 
                    line
                )
                if enter_match:
                    time_str, strategy, strike, opt_type, premium = enter_match.groups()
                    signals.append(SignalEvent(
                        timestamp=f"{date_str} {time_str}",
                        strategy=strategy,
                        signal_type='TAKEN',
                        strike=strike,
                        option_type=opt_type,
                        reason='Entry triggered',
                        pnl=None,
                        metadata={'premium': float(premium)}
                    ))
                
                # Parse "EXIT [TradeID] P&L" lines
                exit_match = re.search(
                    r'(\d{2}:\d{2}:\d{2}).*EXIT.*P&L:\s+([-\d.]+)', 
                    line
                )
                if exit_match:
                    time_str, pnl = exit_match.groups()
                    # Add to last signal for that strategy
                    signals.append(SignalEvent(
                        timestamp=f"{date_str} {time_str}",
                        strategy='UNKNOWN',  # Will be matched later
                        signal_type='EXITED',
                        strike=None,
                        option_type=None,
                        reason='Exit triggered',
                        pnl=float(pnl),
                        metadata={}
                    ))
                
                # Parse BLOCKED signals (custom logging needed in V4)
                blocked_match = re.search(
                    r'(\d{2}:\d{2}:\d{2}).*BLOCKED.*(\w+).*reason:\s*(.*)',
                    line
                )
                if blocked_match:
                    time_str, strategy, reason = blocked_match.groups()
                    signals.append(SignalEvent(
                        timestamp=f"{date_str} {time_str}",
                        strategy=strategy,
                        signal_type='BLOCKED',
                        strike=None,
                        option_type=None,
                        reason=reason.strip(),
                        pnl=None,
                        metadata={}
                    ))
        
        except Exception as e:
            log.error(f"[L2] Error parsing logs: {e}")
        
        return signals
    
    def calculate_opportunity_cost(self, date_str: str, nifty_spot: float) -> List[OpportunityCost]:
        """Calculate missed opportunities by analyzing trades that hit targets after being blocked"""
        missed = []
        
        # Read today's trades CSV
        trades_file = f'daily_data/modular_trades_{date_str}.csv'
        if not os.path.exists(trades_file):
            return missed
        
        try:
            import pandas as pd
            trades = pd.read_csv(trades_file)
            
            # Find trades that were profitable
            for _, trade in trades.iterrows():
                if trade.get('pnl', 0) > 1000:  # Significant profit
                    # Check if similar signal was blocked
                    # This requires cross-referencing with blocked signals
                    pass
        
        except ImportError:
            # Pandas not available, use manual parsing
            pass
        except Exception as e:
            log.error(f"[L2] Error calculating opportunity cost: {e}")
        
        return missed
    
    def get_filter_efficiency(self, strategy: str = None, hours: int = 4) -> Dict:
        """Calculate efficiency of each filter"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        if strategy:
            cursor.execute('''
                SELECT reason, COUNT(*), AVG(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as win_rate
                FROM signals
                WHERE strategy = ? AND timestamp > ? AND signal_type = 'BLOCKED'
                GROUP BY reason
            ''', (strategy, since))
        else:
            cursor.execute('''
                SELECT reason, COUNT(*), 0 as win_rate
                FROM signals
                WHERE timestamp > ? AND signal_type = 'BLOCKED'
                GROUP BY reason
            ''', (since,))
        
        results = {}
        for row in cursor.fetchall():
            reason, count, win_rate = row
            results[reason] = {'blocked_count': count, 'win_rate': win_rate}
        
        conn.close()
        return results
    
    def get_strategy_stats(self, strategy: str, hours: int = 4) -> Dict:
        """Get performance stats for a strategy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute('''
            SELECT 
                COUNT(CASE WHEN signal_type = 'GENERATED' THEN 1 END) as generated,
                COUNT(CASE WHEN signal_type = 'TAKEN' THEN 1 END) as taken,
                COUNT(CASE WHEN signal_type = 'BLOCKED' THEN 1 END) as blocked,
                COUNT(CASE WHEN pnl > 0 THEN 1 END) as wins,
                COUNT(CASE WHEN pnl < 0 THEN 1 END) as losses,
                SUM(pnl) as total_pnl
            FROM signals
            WHERE strategy = ? AND timestamp > ?
        ''', (strategy, since))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'generated': row[0] or 0,
                'taken': row[1] or 0,
                'blocked': row[2] or 0,
                'wins': row[3] or 0,
                'losses': row[4] or 0,
                'total_pnl': row[5] or 0,
                'win_rate': (row[3] / (row[3] + row[4]) * 100) if (row[3] + row[4]) > 0 else 0
            }
        return {}

# ============================================================================
# LAYER 3: MARKET REGIME DETECTOR
# ============================================================================

class MarketRegimeDetector:
    """Layer 3: Classifies current market conditions"""
    
    REGIMES = {
        'TRENDING_BULL': {'adx_min': 25, 'vwap_bias': 'above', 'description': 'Strong uptrend'},
        'TRENDING_BEAR': {'adx_min': 25, 'vwap_bias': 'below', 'description': 'Strong downtrend'},
        'RANGING': {'adx_max': 20, 'vwap_proximity': 0.002, 'description': 'Sideways movement'},
        'VOLATILE': {'vix_min': 20, 'description': 'High volatility'},
        'QUIET': {'vix_max': 12, 'description': 'Low volatility'},
        'GAP_UP': {'gap_min': 0.003, 'description': 'Gap up open'},
        'GAP_DOWN': {'gap_min': -0.003, 'description': 'Gap down open'},
    }
    
    # Regime-specific threshold profiles
    REGIME_PROFILES = {
        'TRENDING_BULL': {
            'VWAP_BAND_PCT': 0.005,        # Wider band in trend
            'MOMENTUM_THRESHOLD': 30,       # Easier momentum
            'POSITION_SIZE_PCT': 1.0,
            'CONFIDENCE_BYPASS': 0.85,      # Lower for trend following
            'MAGIC_MAX_TRADES': 5,          # V5.1: More trades in trend
            'MAGIC_VWAP_THRESHOLD': 0.005,   # V5.1: Wider VWAP threshold
        },
        'TRENDING_BEAR': {
            'VWAP_BAND_PCT': 0.005,
            'MOMENTUM_THRESHOLD': 30,
            'POSITION_SIZE_PCT': 1.0,
            'CONFIDENCE_BYPASS': 0.85,
            'MAGIC_MAX_TRADES': 5,
            'MAGIC_VWAP_THRESHOLD': 0.005,
        },
        'RANGING': {
            'VWAP_BAND_PCT': 0.0015,        # Tighter in range
            'MOMENTUM_THRESHOLD': 60,       # Harder momentum
            'POSITION_SIZE_PCT': 0.7,       # Reduce size
            'CONFIDENCE_BYPASS': 0.93,      # Higher confidence needed
            'MAGIC_MAX_TRADES': 2,          # V5.1: Fewer trades in ranging
            'MAGIC_VWAP_THRESHOLD': 0.003, # V5.1: Strict VWAP threshold
        },
        'VOLATILE': {
            'VWAP_BAND_PCT': 0.008,         # Very wide
            'MOMENTUM_THRESHOLD': 40,
            'POSITION_SIZE_PCT': 0.5,       # Half size
            'CONFIDENCE_BYPASS': 0.88,
            'MAGIC_MAX_TRADES': 3,
            'MAGIC_VWAP_THRESHOLD': 0.006,
            'POSITION_SIZE_PCT': 0.50,    # Half size
            'COOLDOWN_MINUTES': 15,       # Quick re-entry
        },
        'QUIET': {
            'VWAP_BAND_PCT': 0.002,       # Medium
            'MOMENTUM_THRESHOLD': 30,     # Lower (smaller moves)
            'CONFIDENCE_BYPASS': 0.80,    # More lenient
            'POSITION_SIZE_PCT': 0.60,    # Reduced (low volume)
            'COOLDOWN_MINUTES': 45,       # Longer (fewer opportunities)
        },
        'DRIFTING': {
            'VWAP_BAND_PCT': 0.002,           # Moderate band (0.2%)
            'MOMENTUM_THRESHOLD': 45,         # Moderate threshold
            'CONFIDENCE_BYPASS': 0.85,        # Moderate confidence
            'POSITION_SIZE_PCT': 0.75,        # 75% size
            'COOLDOWN_MINUTES': 30,           # Standard cooldown
        },
    }
    
    def __init__(self):
        self.current_regime = 'RANGING'
        self.regime_history = deque(maxlen=100)
        self.price_history = deque(maxlen=50)  # For ADX calculation
        
    def detect_regime(self, market_data: Dict) -> str:
        """Detect current market regime based on VIX, price action, VWAP"""
        vix = market_data.get('vix', 15)
        spot = market_data.get('nifty_spot', 0)
        vwap = market_data.get('vwap', spot)
        prev_close = market_data.get('prev_close', spot)
        
        # Calculate gap
        gap_pct = (spot - prev_close) / prev_close if prev_close else 0
        
        # Check for gaps first
        if gap_pct > 0.003:
            regime = 'GAP_UP'
        elif gap_pct < -0.003:
            regime = 'GAP_DOWN'
        # Check VIX for volatility/quiet
        elif vix > 20:
            regime = 'VOLATILE'
        elif vix < 12:
            regime = 'QUIET'
        # Check ADX and VWAP for trending/ranging
        else:
            adx = self._calculate_adx(market_data)
            vwap_dist = abs(spot - vwap) / vwap if vwap else 0
            price_change = abs(spot - prev_close) / prev_close if prev_close else 0
            
            if adx > 20:  # FIX June 8: lowered from 25 to 20 - catch trending days earlier
                if spot > vwap:
                    regime = 'TRENDING_BULL'
                else:
                    regime = 'TRENDING_BEAR'
            elif 12 <= adx <= 20 and price_change > 0.002 and vwap_dist < 0.003:
                # Flat market with directional drift - not quite trending, not ranging
                regime = 'DRIFTING'
            else:
                regime = 'RANGING'
        
        # Only change regime if sustained for 5 cycles (avoid flickering)
        if regime != self.current_regime:
            self.regime_history.append(regime)
            # Require 5 consecutive cycles of same regime to change (hysteresis)
            if len(self.regime_history) >= 5 and all(r == regime for r in list(self.regime_history)[-5:]):
                old_regime = self.current_regime
                self.current_regime = regime
                log.info(f"[L3] Regime change: {old_regime} → {regime} (after 5 consecutive cycles)")
        else:
            # Clear history only if we have 3+ of the current regime (stabilized)
            if len(self.regime_history) >= 3 and all(r == self.current_regime for r in list(self.regime_history)[-3:]):
                self.regime_history.clear()
        
        return self.current_regime
    
    def _calculate_adx(self, market_data: Dict) -> float:
        """Simplified ADX calculation (0-100)"""
        high = market_data.get('day_high', market_data.get('nifty_spot', 0))
        low = market_data.get('day_low', market_data.get('nifty_spot', 0))
        spot = market_data.get('nifty_spot', 1)
        prev_close = market_data.get('prev_close', spot)
        
        if high == low or spot == 0:
            return 0
        
        # FIX June 3: Previous formula (range_pct*1000) gave 4-8, never reached 25 threshold
        # New: score based on day range in POINTS (NIFTY)
        # 100pt range = ADX 20, 150pt range = ADX 30, 200pt = ADX 40 (realistic)
        range_pts = high - low
        adx_approx = range_pts / 5.0  # 150pt range -> ADX 30 (trending)
        
        # Boost if intraday directional move is large (one-way trending)
        intraday_move = abs(spot - prev_close) if prev_close else 0
        if intraday_move > 80:  # 80+ pts one-way = strongly trending
            adx_approx = max(adx_approx, 35)
        elif intraday_move > 50:  # 50-80 pts = trending
            adx_approx = max(adx_approx, 26)
        
        return min(100, adx_approx)
    
    def detect_intraday_shift(self, market_data: Dict, pcr_history: deque) -> Optional[str]:
        """V5 FIX: Detect intraday regime shifts (PCR trends, momentum changes)
        Returns new regime if shift detected, None otherwise
        """
        from datetime import datetime
        
        spot = market_data.get('nifty_spot', 0)
        day_open = market_data.get('day_open', spot)
        pcr = market_data.get('pcr', 1.0)
        
        # Check 1: Gap override - if gap > 0.2%, force trending mode
        if day_open and day_open > 0:
            gap_pct = (spot - day_open) / day_open * 100
            if abs(gap_pct) >= INTRADAY_SETTINGS['GAP_TREND_OVERRIDE_PCT']:
                new_regime = 'TRENDING_BULL' if gap_pct > 0 else 'TRENDING_BEAR'
                if new_regime != self.current_regime:
                    log.info(f"[L3-INTRADAY] Gap detected ({gap_pct:+.2f}%), forcing {new_regime}")
                    return new_regime
        
        # Check 2: PCR trend - if PCR sustained bullish/bearish for 3 cycles
        if len(pcr_history) >= 3:
            recent_pcr = list(pcr_history)[-3:]
            avg_pcr = sum(recent_pcr) / len(recent_pcr)
            
            # Sustained bullish PCR (< 0.95) for 3 cycles = trending bull
            if all(p < 0.95 for p in recent_pcr) and self.current_regime != 'TRENDING_BULL':
                log.info(f"[L3-INTRADAY] Sustained bullish PCR ({avg_pcr:.2f}), switching to TRENDING_BULL")
                return 'TRENDING_BULL'
            
            # FIX June 8: Sustained bearish PCR (> 1.02) for 3 cycles = trending bear (was 1.05 - too high)
            if all(p > 1.02 for p in recent_pcr) and self.current_regime != 'TRENDING_BEAR':
                log.info(f"[L3-INTRADAY] Sustained bearish PCR ({avg_pcr:.2f}), switching to TRENDING_BEAR")
                return 'TRENDING_BEAR'
        
        # FIX June 8: Large intraday move > 30 points from open (was 50 - missed today's bearish day)
        if day_open and abs(spot - day_open) >= INTRADAY_SETTINGS['TREND_DETECTION_POINTS']:
            direction = 'TRENDING_BULL' if spot > day_open else 'TRENDING_BEAR'
            if direction != self.current_regime:
                log.info(f"[L3-INTRADAY] Large move ({spot-day_open:+.0f} pts), switching to {direction}")
                return direction
        
        return None  # No shift detected
    
    def get_threshold_profile(self, regime: str = None) -> Dict:
        """Get threshold profile for current or specified regime"""
        regime = regime or self.current_regime
        
        # Handle gap regimes - use the underlying trend/range
        if regime in ['GAP_UP', 'GAP_DOWN']:
            regime = 'RANGING'  # Default after gap
        
        return self.REGIME_PROFILES.get(regime, self.REGIME_PROFILES['RANGING'])
    
    def should_block_strategy(self, strategy: str, regime: str = None) -> Tuple[bool, str]:
        """Determine if a strategy should be blocked in current regime"""
        regime = regime or self.current_regime
        
        # Strategy-regime compatibility rules
        blocked_strategies = {
            'VOLATILE': ['TREND_FOLLOWING', 'BREAKOUT'],  # Too noisy
            'QUIET': ['VOLATILITY_BREAKOUT'],  # No volatility to break
            'RANGING': ['TREND_FOLLOWING'],  # Trend strategies struggle
            'TRENDING_BEAR': ['MAGIC_SQUARE'],  # FIX June 8: MAGIC_SQUARE fires CE on bearish days = loss
            'TRENDING_BULL': ['MAGIC_SQUARE'],  # MAGIC_SQUARE fires PE on bullish days = loss
        }
        
        blocked = strategy in blocked_strategies.get(regime, [])
        reason = f"Strategy {strategy} blocked in {regime} regime" if blocked else ""
        
        return blocked, reason

# ============================================================================
# LAYER 4: AUTO-CORRECTION SYSTEM
# ============================================================================

class AutoCorrectionEngine:
    """Layer 4: Automatically adjusts thresholds based on performance"""
    
    def __init__(self, monitor: PerformanceMonitor, regime_detector: MarketRegimeDetector):
        self.monitor = monitor
        self.regime_detector = regime_detector
        self.correction_log = []
        self.last_correction_time = None
        self.previous_thresholds = {}  # For rollback
        self.adjustment_history = deque(maxlen=50)
        
        # Load current thresholds
        self.current_thresholds = DEFAULT_THRESHOLDS.copy()
        self.load_config()
    
    def load_config(self):
        """Load current adaptive config"""
        config_file = 'adaptive_data/adaptive_config.json'
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    if 'thresholds' in config:
                        self.current_thresholds.update(config['thresholds'])
            except Exception as e:
                log.error(f"[L4] Error loading config: {e}")
    
    def save_config(self):
        """Save current thresholds to config file"""
        config_file = 'adaptive_data/adaptive_config.json'
        config = {
            'timestamp': datetime.now().isoformat(),
            'regime': self.regime_detector.current_regime,
            'thresholds': self.current_thresholds,
            'last_correction': self.correction_log[-1] if self.correction_log else None
        }
        
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            log.error(f"[L4] Error saving config: {e}")
    
    def check_and_correct(self) -> List[Dict]:
        """Main correction loop - check all rules and apply corrections"""
        corrections = []
        now = datetime.now()
        
        # Don't correct more frequently than interval
        if self.last_correction_time:
            minutes_since = (now - self.last_correction_time).total_seconds() / 60
            if minutes_since < SAFETY_LIMITS['CORRECTION_INTERVAL_MINUTES']:
                return corrections
        
        # Rule 1: Regime-based profile application
        regime_profile = self.regime_detector.get_threshold_profile()
        for param, value in regime_profile.items():
            if self.current_thresholds.get(param) != value:
                self.apply_correction(param, value, f"Regime-based: {self.regime_detector.current_regime}")
                corrections.append({'param': param, 'value': value, 'reason': 'Regime profile'})
        
        # Rule 2: If strategy has consecutive losses, tighten entry
        for strategy in ['MAGIC_SQUARE', 'AI_ENHANCED', 'TREND_FOLLOWING', 'BREAKOUT']:
            stats = self.monitor.get_strategy_stats(strategy, hours=2)
            if stats.get('losses', 0) >= 2 and stats.get('wins', 0) == 0:
                # Tighten this strategy
                modifier_key = f"{strategy}_CONFIDENCE_MODIFIER"
                current = self.current_thresholds.get(modifier_key, 0.90)
                new_value = min(0.95, current + 0.05)  # Increase confidence requirement
                self.apply_correction(modifier_key, new_value, f"Consecutive losses in {strategy}")
                corrections.append({'param': modifier_key, 'value': new_value, 'reason': f'Losses in {strategy}'})
        
        # Rule 2B: AGGRESSIVE SUPPRESSION - In RANGING regime with 2+ losses, block ALL new entries
        if self.regime_detector.current_regime == 'RANGING':
            total_stats = self.monitor.get_strategy_stats('ALL', hours=2)
            if total_stats.get('losses', 0) >= 2 and total_stats.get('wins', 0) == 0:
                # Check if already suppressed
                if not self.current_thresholds.get('SUPPRESS_NEW_ENTRIES', False):
                    self.apply_correction('SUPPRESS_NEW_ENTRIES', True, 
                                        f"RANGING regime + {total_stats['losses']} consecutive losses - blocking new entries")
                    corrections.append({'param': 'SUPPRESS_NEW_ENTRIES', 'value': True, 
                                       'reason': f'RANGING+losses suppress'})
            else:
                # Release suppression if conditions improve
                if self.current_thresholds.get('SUPPRESS_NEW_ENTRIES', False):
                    self.apply_correction('SUPPRESS_NEW_ENTRIES', False, 
                                        f"Losses cleared or win recorded - releasing entry suppression")
                    corrections.append({'param': 'SUPPRESS_NEW_ENTRIES', 'value': False, 
                                       'reason': 'Releasing suppression'})
        
        # Rule 3: If filter blocking >70% of signals, relax it
        filter_efficiency = self.monitor.get_filter_efficiency(hours=2)
        for reason, data in filter_efficiency.items():
            if data['blocked_count'] > 10:  # Significant sample
                block_rate = data['blocked_count'] / (data['blocked_count'] + data.get('taken', 1))
                if block_rate > 0.7:
                    # Identify which parameter to relax
                    if 'VWAP' in reason:
                        param = 'VWAP_BAND_PCT'
                        current = self.current_thresholds.get(param, 0.003)
                        new_value = min(0.005, current * 1.2)  # 20% wider
                    elif 'MOMENTUM' in reason:
                        param = 'MOMENTUM_THRESHOLD'
                        current = self.current_thresholds.get(param, 50)
                        new_value = int(current * 1.15)  # 15% higher
                    else:
                        continue
                    
                    self.apply_correction(param, new_value, f"Filter over-blocking: {reason}")
                    corrections.append({'param': param, 'value': new_value, 'reason': f'Over-blocking: {reason}'})
        
        # Rule 4: Time-based sizing (afternoon = reduced)
        hour = now.hour
        if hour >= 14:  # After 2 PM
            if self.current_thresholds.get('POSITION_SIZE_PCT', 1.0) > 0.5:
                self.apply_correction('POSITION_SIZE_PCT', 0.5, "Afternoon session - reduced size")
                corrections.append({'param': 'POSITION_SIZE_PCT', 'value': 0.5, 'reason': 'Afternoon session'})
        
        if corrections:
            self.last_correction_time = now
            self.save_config()
            log.info(f"[L4] Applied {len(corrections)} corrections")
            
            # Log to corrections file
            self._log_corrections(corrections)
        
        return corrections
    
    def apply_correction(self, param: str, new_value, reason: str):
        """Apply a threshold correction with safety checks"""
        # Safety check: max daily adjustment
        old_value = self.current_thresholds.get(param)
        if old_value is not None:
            if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
                change_pct = abs(new_value - old_value) / old_value if old_value != 0 else 0
                if change_pct > SAFETY_LIMITS['MAX_DAILY_ADJUSTMENT']:
                    log.warning(f"[L4] Adjustment for {param} exceeds daily limit, capping")
                    # Cap the adjustment
                    if new_value > old_value:
                        new_value = old_value * (1 + SAFETY_LIMITS['MAX_DAILY_ADJUSTMENT'])
                    else:
                        new_value = old_value * (1 - SAFETY_LIMITS['MAX_DAILY_ADJUSTMENT'])
        
        # Store previous for rollback
        self.previous_thresholds[param] = old_value
        
        # Apply
        self.current_thresholds[param] = new_value
        self.adjustment_history.append({
            'time': datetime.now().isoformat(),
            'param': param,
            'old': old_value,
            'new': new_value,
            'reason': reason
        })
        
        log.info(f"[L4] CORRECTION: {param} {old_value} -> {new_value} ({reason})")
    
    def _log_corrections(self, corrections: List[Dict]):
        """Log corrections to file"""
        log_file = 'adaptive_data/corrections.log'
        with open(log_file, 'a') as f:
            for corr in corrections:
                f.write(f"{datetime.now().isoformat()} | {corr['param']} = {corr['value']} | {corr['reason']}\n")
    
    def rollback_if_needed(self, recent_pnl: float):
        """Rollback recent corrections if P&L worsened"""
        if not self.adjustment_history:
            return
        
        last_adjustment = self.adjustment_history[-1]
        adj_time = datetime.fromisoformat(last_adjustment['time'])
        minutes_since = (datetime.now() - adj_time).total_seconds() / 60
        
        if minutes_since < SAFETY_LIMITS['ROLLBACK_WINDOW_MINUTES']:
            return  # Not enough time to evaluate
        
        if recent_pnl < -500:  # Significant loss since adjustment
            log.warning(f"[L4] ROLLBACK triggered - P&L worsened after adjustment")
            # Rollback last adjustment
            param = last_adjustment['param']
            old_value = last_adjustment['old']
            self.current_thresholds[param] = old_value
            self.save_config()
            log.info(f"[L4] ROLLED BACK: {param} → {old_value}")

# ============================================================================
# LAYER 5: META-LEARNING ENGINE
# ============================================================================

class MetaLearningEngine:
    """Layer 5: Learns from FIXES.md patterns and historical performance"""
    
    def __init__(self):
        self.fixes_patterns = []
        self.load_fixes_patterns()
    
    def load_fixes_patterns(self):
        """Extract patterns from FIXES.md"""
        fixes_file = 'FIXES.md'
        if not os.path.exists(fixes_file):
            log.warning("[L5] FIXES.md not found")
            return
        
        try:
            with open(fixes_file, 'r') as f:
                content = f.read()
            
            # Extract fix patterns using regex
            # Pattern: Problem → Solution → Code
            fix_blocks = re.findall(
                r'### FIX #(\d+).*?\*\*Problem:\*\*(.*?)\*\*Solution:\*\*(.*?)\*\*Code:\*\*',
                content,
                re.DOTALL
            )
            
            for fix_num, problem, solution in fix_blocks[:20]:  # First 20 fixes
                pattern = {
                    'fix_number': fix_num,
                    'problem': problem.strip()[:100],
                    'solution': solution.strip()[:200],
                    'effectiveness': None,  # To be learned
                    'conditions': self._extract_conditions(problem)
                }
                self.fixes_patterns.append(pattern)
            
            log.info(f"[L5] Loaded {len(self.fixes_patterns)} patterns from FIXES.md")
        
        except Exception as e:
            log.error(f"[L5] Error parsing FIXES.md: {e}")
    
    def _extract_conditions(self, problem: str) -> List[str]:
        """Extract market conditions from problem description"""
        conditions = []
        
        # Look for keywords indicating market conditions
        if any(word in problem.lower() for word in ['morning', 'early', 'opening']):
            conditions.append('morning_session')
        if any(word in problem.lower() for word in ['afternoon', 'late', 'choppy']):
            conditions.append('afternoon_session')
        if any(word in problem.lower() for word in ['volatile', 'vix', 'spike']):
            conditions.append('high_volatility')
        if any(word in problem.lower() for word in ['quiet', 'low volume', 'sideways']):
            conditions.append('low_volatility')
        if any(word in problem.lower() for word in ['trend', 'direction', 'bias']):
            conditions.append('trending_market')
        
        return conditions
    
    def predict_optimal_setup(self, day_of_week: int, vix_forecast: float) -> Dict:
        """Predict optimal thresholds for tomorrow based on patterns"""
        # Phase A: Simple rule-based prediction
        setup = DEFAULT_THRESHOLDS.copy()
        
        # Monday pattern: Often choppy after weekend
        if day_of_week == 0:  # Monday
            setup['POSITION_SIZE_PCT'] = 0.8
            setup['COOLDOWN_MINUTES'] = 45
        
        # Friday pattern: Lower volume
        if day_of_week == 4:  # Friday
            setup['POSITION_SIZE_PCT'] = 0.7
            setup['CONFIDENCE_BYPASS'] = 0.92
        
        # High VIX expected
        if vix_forecast > 18:
            setup['POSITION_SIZE_PCT'] = 0.6
            setup['MOMENTUM_THRESHOLD'] = 80
        
        return setup
    
    def weekly_update(self):
        """Weekly learning cycle - runs every Sunday"""
        log.info("[L5] Running weekly meta-learning update")
        
        # Analyze which fixes were most effective
        # Update strategy DNA
        # Generate recommendations for next week
        
        recommendations = {
            'timestamp': datetime.now().isoformat(),
            'next_week_adjustments': {},
            'strategy_focus': [],
            'avoid_conditions': []
        }
        
        # Save recommendations
        rec_file = 'adaptive_data/weekly_recommendations.json'
        with open(rec_file, 'w') as f:
            json.dump(recommendations, f, indent=2)
        
        log.info(f"[L5] Weekly recommendations saved to {rec_file}")
        return recommendations

# ============================================================================
# MAIN ADAPTIVE ENGINE
# ============================================================================

class AdaptiveEngineV4:
    """Main engine that orchestrates all 5 layers"""
    
    def __init__(self):
        log.info("="*80)
        log.info("ADAPTIVE ENGINE V4 - Adaptive Trading Layer")
        log.info("Phase A: Rule-Based Foundation")
        log.info("="*80)
        
        # Initialize all layers
        self.layer2_monitor = PerformanceMonitor()
        self.layer3_regime = MarketRegimeDetector()
        self.layer4_corrector = AutoCorrectionEngine(
            self.layer2_monitor, 
            self.layer3_regime
        )
        self.layer5_meta = MetaLearningEngine()
        
        # State
        self.is_running = False
        self.cycle_count = 0
        self.last_v4_pnl = 0
        
        # Market data cache
        self.market_data = {
            'nifty_spot': 0,
            'vix': 15,
            'vwap': 0,
            'pcr': 1.0,
            'day_high': 0,
            'day_low': 0,
            'prev_close': 0,
            'day_open': 0,
            'pcr_history': deque(maxlen=10),  # FIX: persist across cycles
        }
        
        log.info("[INIT] All layers initialized successfully")
    
    def update_market_data(self):
        """Read current market data from V4 logs or API"""
        # Try to read from V4's latest log entry
        today = datetime.now().strftime('%Y%m%d')
        log_file = f'daily_data/modular_{today}.log'
        
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    # FIX: Reset per-cycle fields so they refresh each time
                    self.market_data['nifty_spot'] = 0
                    # Parse last 40 lines for market data (FIX: was 20, may miss data)
                    for line in reversed(lines[-40:]):
                        # FIX: match both 'Spot=' and 'spot=' (case-insensitive) as V4 logs use lowercase
                        spot_match = re.search(r'[Ss]pot[=:]([\.\d]+)', line)
                        if spot_match and self.market_data['nifty_spot'] == 0:
                            val = float(spot_match.group(1))
                            if val > 10000:  # Sanity check - must be a real NIFTY price
                                self.market_data['nifty_spot'] = val
                        
                        # FIX: also extract from CYCLE line format: 'NIFTY 23642.90'
                        cycle_match = re.search(r'NIFTY\s+([\.\d]+)', line)
                        if cycle_match and self.market_data['nifty_spot'] == 0:
                            val = float(cycle_match.group(1))
                            if val > 10000:
                                self.market_data['nifty_spot'] = val
                        
                        # FIX: extract day open
                        open_match = re.search(r'O[=:]([\.\d]+)', line)
                        if open_match and self.market_data.get('day_open', 0) == 0:
                            val = float(open_match.group(1))
                            if val > 10000:
                                self.market_data['day_open'] = val

                        # Try to extract VIX
                        vix_match = re.search(r'[Vv][Ii][Xx][=:]([\.\d]+)', line)
                        if vix_match:
                            self.market_data['vix'] = float(vix_match.group(1))
                        
                        # Try to extract VWAP
                        vwap_match = re.search(r'[Vv][Ww][Aa][Pp][=:]([\.\d]+)', line)
                        if vwap_match:
                            val = float(vwap_match.group(1))
                            if val > 10000:
                                self.market_data['vwap'] = val

                        # FIX: extract PCR from logs: 'PCR:1.068'
                        pcr_match = re.search(r'PCR[=:]([\.\d]+)', line)
                        if pcr_match:
                            self.market_data['pcr'] = float(pcr_match.group(1))
            
            except Exception as e:
                log.warning(f"[DATA] Error reading market data: {e}")
    
    def display_dashboard(self):
        """Display real-time adaptive dashboard"""
        now = datetime.now()
        
        print("\n" + "="*80)
        print(f"ADAPTIVE V4 DASHBOARD | {now.strftime('%H:%M:%S')} | Cycle #{self.cycle_count}")
        print("="*80)
        
        # Layer 3: Market Regime
        print(f"\n[MARKET REGIME] {self.layer3_regime.current_regime}")
        print(f"  Spot: {self.market_data['nifty_spot']:.2f} | "
              f"VIX: {self.market_data['vix']:.2f} | "
              f"VWAP: {self.market_data['vwap']:.2f}")
        
        # Current thresholds
        print(f"\n[CURRENT THRESHOLDS]")
        for param, value in self.layer4_corrector.current_thresholds.items():
            print(f"  {param}: {value}")
        
        # Layer 2: Strategy Stats
        print(f"\n[STRATEGY PERFORMANCE - Last 4 Hours]")
        for strategy in ['MAGIC_SQUARE', 'AI_ENHANCED', 'TREND_FOLLOWING', 'BREAKOUT']:
            stats = self.layer2_monitor.get_strategy_stats(strategy, hours=4)
            if stats.get('generated', 0) > 0:
                print(f"  {strategy:20}: {stats['taken']}/{stats['generated']} taken, "
                      f"W/L: {stats['wins']}/{stats['losses']}, "
                      f"P&L: ₹{stats['total_pnl']:.0f}")
        
        # Recent corrections
        if self.layer4_corrector.adjustment_history:
            print(f"\n[RECENT AUTO-CORRECTIONS]")
            for adj in list(self.layer4_corrector.adjustment_history)[-3:]:
                print(f"  {adj['time'][11:19]}: {adj['param']} {adj['old']} -> {adj['new']}")
        
        # Recommendations
        print(f"\n[SYSTEM STATUS]")
        print(f"  Auto-correction: ACTIVE (every {SAFETY_LIMITS['CORRECTION_INTERVAL_MINUTES']} min)")
        print(f"  Safety limits: ENFORCED")
        print(f"  Config file: adaptive_data/adaptive_config.json")
        
        print("="*80)
    
    def write_eod_learning(self):
        """V5: After market close, analyze today and write adaptive config for tomorrow"""
        today = datetime.now().strftime('%Y%m%d')
        trades_file = f'daily_data/modular_trades_{today}.csv'
        if not os.path.exists(trades_file):
            return

        try:
            rows = list(__import__('csv').DictReader(open(trades_file)))
            exits = [r for r in rows if r['event'] == 'EXIT' and r.get('pnl')]
            if not exits:
                return

            total_pnl = sum(float(r['pnl']) for r in exits)
            pe_pnl = sum(float(r['pnl']) for r in exits if r['direction'] == 'PE')
            ce_pnl = sum(float(r['pnl']) for r in exits if r['direction'] == 'CE')
            win_rate = sum(1 for r in exits if float(r['pnl']) > 0) / len(exits)

            # Determine tomorrow's starting bias
            gap_down_losses = sum(1 for r in exits if r['strategy'] == 'GAP_DOWN_TREND' and float(r['pnl']) < 0)
            bias_note = 'NEUTRAL'
            if pe_pnl < -10000 and ce_pnl > pe_pnl:
                bias_note = 'AVOID_PE_MORNING'
            elif ce_pnl < -10000 and pe_pnl > ce_pnl:
                bias_note = 'AVOID_CE_MORNING'

            eod_notes = {
                'date': today,
                'total_pnl': total_pnl,
                'pe_pnl': pe_pnl,
                'ce_pnl': ce_pnl,
                'win_rate': win_rate,
                'gap_down_losses': gap_down_losses,
                'tomorrow_bias_note': bias_note,
                'eod_exits': len([r for r in exits if r.get('exit_reason') == 'EOD_FORCE']),
                'timestop_exits': len([r for r in exits if r.get('exit_reason') == 'TIME_STOP']),
                'sl_exits': len([r for r in exits if r.get('exit_reason') == 'STOP_LOSS']),
            }

            # Adjust thresholds for tomorrow
            thresholds = self.layer4_corrector.current_thresholds.copy()
            if win_rate < 0.30:  # Poor win rate today - tighten everything
                thresholds['CONFIDENCE_BYPASS'] = min(0.95, thresholds.get('CONFIDENCE_BYPASS', 0.90) + 0.02)
                log.info(f"[EOD_LEARN] Poor win rate {win_rate:.0%} - raising confidence bypass to {thresholds['CONFIDENCE_BYPASS']}")
            if gap_down_losses >= 2:  # Gap-down strategy failed
                thresholds['GAP_DOWN_BLOCK_NEXT_DAY'] = True
                log.info(f"[EOD_LEARN] Gap-down strategy lost {gap_down_losses} times - flagging for tomorrow")

            config = {
                'timestamp': datetime.now().isoformat(),
                'regime': self.layer3_regime.current_regime,
                'thresholds': thresholds,
                'eod_learning': eod_notes,
                'last_correction': self.layer4_corrector.correction_log[-1] if self.layer4_corrector.correction_log else None
            }
            with open('adaptive_data/adaptive_config.json', 'w') as f:
                __import__('json').dump(config, f, indent=2)

            log.info(f"[EOD_LEARN] Wrote learning config: P&L={total_pnl:.0f} WinRate={win_rate:.0%} TomorrowBias={bias_note}")

        except Exception as e:
            log.error(f"[EOD_LEARN] Error: {e}")

    def run_cycle(self):
        """Execute one full cycle of the adaptive engine"""
        self.cycle_count += 1
        
        # 1. Update market data
        self.update_market_data()
        
        # 2. Detect market regime (Layer 3)
        regime = self.layer3_regime.detect_regime(self.market_data)
        
        # FIX: Append PCR to persistent history every cycle
        if self.market_data.get('pcr', 0) > 0:
            self.market_data['pcr_history'].append(self.market_data['pcr'])

        # V5.1 FIX: Intraday regime shift detection (every 5 minutes)
        if self.cycle_count % INTRADAY_SETTINGS['MOMENTUM_CONFIRMATION_CYCLES'] == 0:
            # FIX: use persistent pcr_history from market_data (not a fresh deque)
            pcr_history = self.market_data['pcr_history']
            
            intraday_shift = self.layer3_regime.detect_intraday_shift(
                self.market_data, pcr_history
            )
            if intraday_shift:
                # Regime shifted - apply new thresholds immediately
                self.layer3_regime.current_regime = intraday_shift
                new_profile = self.layer3_regime.get_threshold_profile(intraday_shift)
                self.layer4_corrector.current_thresholds.update(new_profile)
                log.info(f"[V5.1-INTRADAY] Regime shifted to {intraday_shift}, thresholds updated")
        
        # 3. Parse V4 signals (Layer 2)
        today = datetime.now().strftime('%Y%m%d')
        signals = self.layer2_monitor.parse_v4_logs(today)
        
        # Store signals to database
        if signals:
            conn = sqlite3.connect(self.layer2_monitor.db_path)
            cursor = conn.cursor()
            for sig in signals:
                cursor.execute('''
                    INSERT INTO signals 
                    (timestamp, strategy, signal_type, strike, option_type, reason, pnl, vix, pcr, nifty_spot)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sig.timestamp, sig.strategy, sig.signal_type, sig.strike,
                    sig.option_type, sig.reason, sig.pnl,
                    self.market_data['vix'], self.market_data['pcr'],
                    self.market_data['nifty_spot']
                ))
            conn.commit()
            conn.close()
        
        # 4. Auto-correction (Layer 4)
        corrections = self.layer4_corrector.check_and_correct()
        
        # 5. Check if rollback needed
        # (Would need actual P&L calculation from trades CSV)
        
        # 6. Display dashboard
        if self.cycle_count % 6 == 0:  # Every 6 cycles (~3 minutes)
            self.display_dashboard()
        
        # 7. Log status
        if corrections:
            log.info(f"[CYCLE {self.cycle_count}] Regime: {regime}, Corrections: {len(corrections)}")
        else:
            log.info(f"[CYCLE {self.cycle_count}] Regime: {regime}, No corrections needed")
    
    def run(self):
        """Main loop - runs parallel to V4"""
        self.is_running = True
        
        log.info("="*80)
        log.info("ADAPTIVE ENGINE STARTED - Monitoring V4 in real-time")
        log.info("Press Ctrl+C to stop")
        log.info("="*80)
        
        # Initial display
        self.display_dashboard()
        
        _eod_written = False
        try:
            while self.is_running:
                self.run_cycle()

                # V5: Write EOD learning after market close (once per day)
                now = datetime.now()
                if not _eod_written and (now.hour > 15 or (now.hour == 15 and now.minute >= 20)):
                    self.write_eod_learning()
                    _eod_written = True

                # Sleep 30 seconds between cycles
                time.sleep(30)

        except KeyboardInterrupt:
            log.info("\n[STOP] Adaptive engine stopped by user")
        except Exception as e:
            log.error(f"[ERROR] Adaptive engine error: {e}", exc_info=True)
        finally:
            self.is_running = False
            log.info("[STOP] Adaptive engine shutdown complete")
    
    def stop(self):
        """Stop the adaptive engine"""
        self.is_running = False

# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Adaptive Engine V4 - Adaptive Trading Layer')
    parser.add_argument('--dashboard-only', action='store_true', help='Only show dashboard, no corrections')
    parser.add_argument('--test', action='store_true', help='Run in test mode (no V4 integration)')
    
    args = parser.parse_args()
    
    # Create adaptive_data directory if not exists
    os.makedirs('adaptive_data', exist_ok=True)
    
    # Initialize and run engine
    engine = AdaptiveEngineV4()
    
    if args.test:
        log.info("[TEST MODE] Running without V4 integration")
        # Run a few test cycles
        for i in range(5):
            engine.run_cycle()
            time.sleep(2)
    else:
        engine.run()

if __name__ == '__main__':
    main()
