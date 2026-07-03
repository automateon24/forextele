#!/usr/bin/env python3
"""
STRATEGY DNA FIXES - June 6, 2026
Optimized DNA configurations for all strategies needing improvement
Target: Fix 3 losing strategies + Optimize top performers
"""

from dataclasses import dataclass
from typing import Dict, Set, Tuple, Optional

@dataclass
class StrategyDNA:
    """Complete DNA for a strategy - timing, exits, filters"""
    name: str
    direction: str
    
    # === TIMING DNA ===
    entry_start: int  # HHMM - earliest entry
    entry_cutoff: int  # HHMM - latest entry
    
    # === EXIT DNA (TSL Settings) ===
    tsl_activate: float  # % to arm TSL
    tsl_trail: float  # % to trail
    target_pct: float  # % hard target
    sl_backstop: float  # % hard stop
    
    # === FILTER DNA ===
    min_confidence: float  # 0.0-1.0
    volume_spike: float  # 1.0+ multiplier
    adx_max: Optional[float]  # Max ADX for mean reversion
    ema_required: bool  # EMA alignment required
    
    # === PREMIUM DNA ===
    min_premium: float  # ₹ minimum
    max_premium: float  # ₹ maximum
    
    # === INDEX-SPECIFIC DNA ===
    allowed_indices: Set[str]
    regime_blocked: Set[str]  # Regimes to avoid
    
    # === NOTES ===
    notes: str

# =============================================================================
# OPTIMIZED DNA FOR 3 LOSING STRATEGIES (Critical Fixes)
# =============================================================================

FIXED_STRATEGY_DNA = {
    
    # === TREND_FOLLOWING - COMPLETELY REWORKED ===
    # Problem: 66% TIME exits, 33% WR
    # Fix: Earlier entry, tighter TSL, volume confirmation
    'TREND_FOLLOWING': StrategyDNA(
        name='TREND_FOLLOWING',
        direction='BOTH',  # Changed from PE to BOTH
        
        # TIMING: Must enter early to allow trend to develop
        entry_start=945,   # 9:45 - earliest possible
        entry_cutoff=1130, # 11:30 - cutoff to avoid TIME exits
        
        # EXITS: Tighter to lock in quick trend moves
        tsl_activate=0.05,  # 5% (lower = earlier TSL activation)
        tsl_trail=0.03,     # 3% (tighter = faster profit lock)
        target_pct=0.25,    # 25% (lower = faster exits)
        sl_backstop=0.25,   # 25% (tighter stop)
        
        # FILTERS: High confidence + volume required
        min_confidence=0.88,  # Higher threshold
        volume_spike=1.4,     # Strong volume confirmation
        adx_max=None,
        ema_required=True,    # EMA 9>21>50 or 9<21<50
        
        # PREMIUM: Moderate range
        min_premium=60,
        max_premium=500,
        
        # INDEX: Works on all but needs volatility
        allowed_indices={'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX'},
        regime_blocked={'HIGH_VOLATILITY'},  # Avoid choppy markets
        
        notes='FIXED: Earlier entry 9:45-11:30, tighter TSL 5%/3%, volume 1.4x, EMA required'
    ),
    
    # === SHORT_UNWIND - PCR REPLACED WITH VOLUME/OI ===
    # Problem: PCR unreliable in 15min data, 40% WR
    # Fix: Replace PCR with Volume + OI change detection
    'SHORT_UNWIND_V2': StrategyDNA(
        name='SHORT_UNWIND_V2',
        direction='CE',  # Long only (short covering = bullish)
        
        # TIMING: Afternoon when shorts unwind
        entry_start=1230,  # 12:30 - post-lunch
        entry_cutoff=1400, # 14:00 - before EOD volatility
        
        # EXITS: Quick profit take (unwinding is fast)
        tsl_activate=0.06,  # 6%
        tsl_trail=0.04,     # 4%
        target_pct=0.30,    # 30% (quick target)
        sl_backstop=0.20,   # 20% (tight stop)
        
        # FILTERS: Volume + OI change (not PCR)
        min_confidence=0.85,
        volume_spike=1.5,     # High volume = conviction
        adx_max=None,
        ema_required=True,    # Price above EMAs
        
        # PREMIUM: Higher min to cover fees
        min_premium=80,
        max_premium=400,
        
        # INDEX: Works best on liquid indices
        allowed_indices={'NIFTY', 'BANKNIFTY', 'FINNIFTY'},
        regime_blocked={'TRENDING_BEAR'},  # Don't fight downtrend
        
        notes='FIXED: Replaced PCR with Volume 1.5x + OI drop, afternoon only 12:30-14:00'
    ),
    
    # === ORDER_BLOCK_REVERSAL - ALREADY FIXED ===
    # Status: 81% WR, +₹3,721 - keep current DNA
    'ORDER_BLOCK_REVERSAL': StrategyDNA(
        name='ORDER_BLOCK_REVERSAL',
        direction='BOTH',
        
        # TIMING: Early-morning only (fixed from 13:00 to 12:15)
        entry_start=1000,   # 10:00 - after opening volatility
        entry_cutoff=1215,  # 12:15 - FIXED cutoff
        
        # EXITS: Standard TSL
        tsl_activate=0.10,
        tsl_trail=0.08,
        target_pct=0.60,
        sl_backstop=0.35,
        
        # FILTERS: Volume required for reversal
        min_confidence=0.84,
        volume_spike=1.3,
        adx_max=None,
        ema_required=False,
        
        # PREMIUM
        min_premium=50,
        max_premium=500,
        
        # INDEX: All indices
        allowed_indices={'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX'},
        regime_blocked=set(),
        
        notes='WORKING: 81% WR after fix, entry cutoff 12:15 prevents TIME exits'
    ),
}

# =============================================================================
# OPTIMIZED DNA FOR TOP PERFORMERS (Reduce TIME Exits)
# =============================================================================

OPTIMIZED_STRATEGY_DNA = {
    
    # === WIDE_RANGE_RIDER - REDUCE TIME EXITS ===
    # Current: +₹18,695, 83.7% WR, 14% TIME exits
    # Goal: Earlier cutoff to improve TSL activation
    'WIDE_RANGE_RIDER': StrategyDNA(
        name='WIDE_RANGE_RIDER',
        direction='BOTH',
        
        # TIMING: Earlier cutoff for TSL activation
        entry_start=945,
        entry_cutoff=1230,  # Changed from 13:00 to 12:30
        
        # EXITS: Wider TSL to let winners run
        tsl_activate=0.07,  # 7% (lower = earlier activation)
        tsl_trail=0.05,     # 5% (wider = more room)
        target_pct=0.50,
        sl_backstop=0.30,
        
        # FILTERS: VWAP confirmation
        min_confidence=0.82,
        volume_spike=1.2,
        adx_max=None,
        ema_required=False,
        
        # PREMIUM
        min_premium=60,
        max_premium=600,
        
        allowed_indices={'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX'},
        regime_blocked={'HIGH_VOLATILITY'},
        
        notes='OPTIMIZED: Entry cutoff 12:30 (was 13:00), wider TSL 7%/5%'
    ),
    
    # === MAGIC_SQUARE - FASTER EXITS ===
    # Current: +₹17,124, 76.8% WR, 23% TIME exits
    # Goal: Faster TSL to avoid TIME exits
    'MAGIC_SQUARE': StrategyDNA(
        name='MAGIC_SQUARE',
        direction='BOTH',
        
        # TIMING: Time windows for optimal magic levels
        entry_start=1030,   # 10:30
        entry_cutoff=1430,  # 14:30 - allows afternoon magic levels
        
        # EXITS: Faster profit take (brokerage death issue)
        tsl_activate=0.05,  # 5% (earlier)
        tsl_trail=0.03,     # 3% (tighter)
        target_pct=0.20,    # 20% (lower for quick exits)
        sl_backstop=0.20,   # 20% (tight stop)
        
        # FILTERS: Higher min premium
        min_confidence=0.85,
        volume_spike=1.0,  # No volume filter for this
        adx_max=None,
        ema_required=False,
        
        # PREMIUM: Higher min to cover fees
        min_premium=100,  # Increased from 80
        max_premium=400,
        
        allowed_indices={'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX'},
        regime_blocked=set(),
        
        notes='OPTIMIZED: Faster TSL 5%/3%, higher min premium ₹100, quicker exits'
    ),
    
    # === MEAN_REVERSION - TIGHTER ADX ===
    # Current: +₹6,560, 77.8% WR, 22% TIME exits
    # Goal: Avoid trending days
    'MEAN_REVERSION': StrategyDNA(
        name='MEAN_REVERSION',
        direction='BOTH',
        
        # TIMING
        entry_start=945,
        entry_cutoff=1300,
        
        # EXITS
        tsl_activate=0.06,
        tsl_trail=0.04,
        target_pct=0.35,
        sl_backstop=0.30,
        
        # FILTERS: Tighter ADX + BB position
        min_confidence=0.82,
        volume_spike=1.3,
        adx_max=25.0,      # Tighter (was 28)
        ema_required=False,
        
        # PREMIUM
        min_premium=45,
        max_premium=400,
        
        allowed_indices={'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX'},
        regime_blocked=set(),
        
        notes='OPTIMIZED: ADX max 25 (tighter), BB 2σ filter active'
    ),
}

# =============================================================================
# DNA FOR UNTESTED STRATEGIES (Ready for Testing)
# =============================================================================

UNTESTED_STRATEGY_DNA = {
    
    # === GAMMA_BLAST - EXPIRY ONLY ===
    'GAMMA_BLAST': StrategyDNA(
        name='GAMMA_BLAST',
        direction='BOTH',
        entry_start=1330,  # Last 2 hours
        entry_cutoff=1430,
        tsl_activate=0.08,
        tsl_trail=0.06,
        target_pct=0.70,   # 2x normal target
        sl_backstop=0.25,
        min_confidence=0.85,
        volume_spike=1.5,  # High volume required
        adx_max=None,
        ema_required=False,
        min_premium=30,    # Cheap OTM
        max_premium=200,
        allowed_indices={'NIFTY', 'BANKNIFTY', 'FINNIFTY'},
        regime_blocked=set(),
        notes='EXPIRY ONLY: Last 2 hours, 2x target, high volume, cheap premiums'
    ),
    
    # === ZERO_HERO - EXPIRY OTM ===
    'ZERO_HERO': StrategyDNA(
        name='ZERO_HERO',
        direction='PE',  # Put only (downside gamma)
        entry_start=1300,
        entry_cutoff=1430,
        tsl_activate=0.10,
        tsl_trail=0.08,
        target_pct=1.00,   # 100% target (hero or zero)
        sl_backstop=0.30,
        min_confidence=0.80,
        volume_spike=1.3,
        adx_max=None,
        ema_required=False,
        min_premium=20,    # Very cheap OTM
        max_premium=50,
        allowed_indices={'NIFTY', 'BANKNIFTY'},
        regime_blocked={'TRENDING_BULL'},  # Don't fight uptrend
        notes='EXPIRY ONLY: Cheap OTM PE, 100% target, high risk/reward'
    ),
    
    # === AI_ENHANCED ===
    'AI_ENHANCED': StrategyDNA(
        name='AI_ENHANCED',
        direction='BOTH',
        entry_start=945,
        entry_cutoff=1430,
        tsl_activate=0.08,
        tsl_trail=0.06,
        target_pct=0.50,
        sl_backstop=0.30,
        min_confidence=0.88,  # High confidence for AI
        volume_spike=1.3,
        adx_max=None,
        ema_required=True,
        min_premium=60,
        max_premium=500,
        allowed_indices={'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX'},
        regime_blocked=set(),
        notes='AI CALIBRATED: PCR 1.33, multi-factor, high confidence 0.88'
    ),
    
    # === BREAKOUT ===
    'BREAKOUT': StrategyDNA(
        name='BREAKOUT',
        direction='PE',  # Start with PE only
        entry_start=945,
        entry_cutoff=1400,
        tsl_activate=0.10,
        tsl_trail=0.08,
        target_pct=0.50,
        sl_backstop=0.30,
        min_confidence=0.85,
        volume_spike=1.4,  # Breakout needs volume
        adx_max=None,
        ema_required=False,
        min_premium=50,
        max_premium=400,
        allowed_indices={'NIFTY', 'BANKNIFTY', 'FINNIFTY'},
        regime_blocked=set(),
        notes='PE ONLY: Volume 1.4x required for breakout confirmation'
    ),
    
    # === ULTIMATE_DAY_HIGH_LOW - WITH FIXES ===
    'ULTIMATE_DAY_HIGH_LOW': StrategyDNA(
        name='ULTIMATE_DAY_HIGH_LOW',
        direction='BOTH',
        entry_start=1000,
        entry_cutoff=1430,
        tsl_activate=0.08,
        tsl_trail=0.06,
        target_pct=0.50,
        sl_backstop=0.30,
        min_confidence=0.80,
        volume_spike=1.5,  # High volume for day extreme breaks
        adx_max=None,
        ema_required=False,
        min_premium=80,
        max_premium=600,
        allowed_indices={'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX'},
        regime_blocked={'TRENDING_BULL', 'TRENDING_BEAR'},  # Avoid trend days
        notes='FIXED: Volume 1.5x, blocked on trend days, day extremes only'
    ),
}

# =============================================================================
# INDEX-SPECIFIC TSL MULTIPLIERS (Apply to all strategies)
# =============================================================================

INDEX_TSL_MULTIPLIERS = {
    'NIFTY':      {'activate': 1.0, 'trail': 1.0, 'target': 1.0},  # Baseline
    'BANKNIFTY':  {'activate': 1.3, 'trail': 1.3, 'target': 1.2},  # 30% more room
    'FINNIFTY':   {'activate': 1.2, 'trail': 1.2, 'target': 1.1},  # 20% more room
    'SENSEX':     {'activate': 1.4, 'trail': 1.4, 'target': 1.3},  # 40% more room
}

def apply_index_dna(dna: StrategyDNA, index: str) -> StrategyDNA:
    """Apply index-specific adjustments to DNA"""
    multipliers = INDEX_TSL_MULTIPLIERS.get(index, {'activate': 1.0, 'trail': 1.0, 'target': 1.0})
    
    # Create adjusted DNA
    adjusted = StrategyDNA(
        name=f"{index}:{dna.name}",
        direction=dna.direction,
        entry_start=dna.entry_start,
        entry_cutoff=dna.entry_cutoff,
        tsl_activate=min(0.20, dna.tsl_activate * multipliers['activate']),
        tsl_trail=min(0.15, dna.tsl_trail * multipliers['trail']),
        target_pct=min(2.50, dna.target_pct * multipliers['target']),
        sl_backstop=dna.sl_backstop,
        min_confidence=dna.min_confidence,
        volume_spike=dna.volume_spike,
        adx_max=dna.adx_max,
        ema_required=dna.ema_required,
        min_premium=dna.min_premium,
        max_premium=dna.max_premium,
        allowed_indices={index},  # Now specific to this index
        regime_blocked=dna.regime_blocked,
        notes=f"{index} {dna.notes}"
    )
    
    return adjusted

# =============================================================================
# COMPLETE DNA MATRIX (4 indices × 15 strategies = 60 combinations)
# =============================================================================

def build_complete_dna_matrix():
    """Build full 60-point DNA matrix"""
    matrix = {}
    
    # Combine all DNA configs
    all_dna = {**FIXED_STRATEGY_DNA, **OPTIMIZED_STRATEGY_DNA, **UNTESTED_STRATEGY_DNA}
    
    for strat_name, base_dna in all_dna.items():
        for idx in base_dna.allowed_indices:
            # Check if strategy blocked for this regime
            key = f"{idx}:{strat_name}"
            matrix[key] = apply_index_dna(base_dna, idx)
    
    return matrix

COMPLETE_DNA_MATRIX = build_complete_dna_matrix()

# =============================================================================
# PRINT SUMMARY
# =============================================================================

if __name__ == "__main__":
    print("=" * 100)
    print("STRATEGY DNA FIXES - June 6, 2026")
    print("=" * 100)
    
    print("\n=== FIXED STRATEGIES (3) ===")
    for name, dna in FIXED_STRATEGY_DNA.items():
        print(f"\n{name}:")
        print(f"  Entry: {dna.entry_start} - {dna.entry_cutoff}")
        print(f"  TSL: {dna.tsl_activate*100:.0f}%/{dna.tsl_trail*100:.0f}%, Target: {dna.target_pct*100:.0f}%")
        print(f"  Filters: Confidence {dna.min_confidence}, Volume {dna.volume_spike}x, EMA: {dna.ema_required}")
        print(f"  Notes: {dna.notes}")
    
    print("\n=== OPTIMIZED STRATEGIES (3) ===")
    for name, dna in OPTIMIZED_STRATEGY_DNA.items():
        print(f"\n{name}:")
        print(f"  Entry: {dna.entry_start} - {dna.entry_cutoff}")
        print(f"  TSL: {dna.tsl_activate*100:.0f}%/{dna.tsl_trail*100:.0f}%, Target: {dna.target_pct*100:.0f}%")
        print(f"  Filters: Confidence {dna.min_confidence}, Volume {dna.volume_spike}x")
        print(f"  Notes: {dna.notes}")
    
    print("\n=== UNTESTED STRATEGIES (5) ===")
    for name, dna in UNTESTED_STRATEGY_DNA.items():
        print(f"\n{name}:")
        print(f"  Entry: {dna.entry_start} - {dna.entry_cutoff}")
        print(f"  TSL: {dna.tsl_activate*100:.0f}%/{dna.tsl_trail*100:.0f}%, Target: {dna.target_pct*100:.0f}%")
        print(f"  Notes: {dna.notes}")
    
    print(f"\n=== COMPLETE MATRIX ===")
    print(f"Total DNA combinations: {len(COMPLETE_DNA_MATRIX)}")
    print(f"Indices: NIFTY, BANKNIFTY, FINNIFTY, SENSEX")
    print(f"Strategies: {len(all_dna)} per index")
    
    print("\n" + "=" * 100)
    print("Ready to implement in BACKTEST_V7_AGGRESSIVE.py")
    print("=" * 100)
