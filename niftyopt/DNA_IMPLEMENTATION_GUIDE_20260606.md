# DNA IMPLEMENTATION GUIDE - June 6, 2026
## Complete DNA Settings for 11 Strategies Needing Fixes

---

## 🎯 STRATEGY CATEGORIES

### 1. FIXED STRATEGIES (3) - Critical Priority
| Strategy | Before | After | Fix Applied |
|----------|--------|-------|-------------|
| **TREND_FOLLOWING** | -₹1,602 (33% WR) | **+₹5K-8K** (projected) | Earlier entry 9:45-11:30, tighter TSL |
| **SHORT_UNWIND_V2** | -₹1,605 (40% WR) | **+₹5K-8K** (projected) | PCR→Volume 1.5x, afternoon only |
| **ORDER_BLOCK_REVERSAL** | -₹2,775 (62.9% WR) | **+₹3,721 (81% WR)** | Entry cutoff 12:15 |

### 2. OPTIMIZED STRATEGIES (3) - High Priority
| Strategy | Current | Target | Optimization |
|----------|---------|--------|--------------|
| **WIDE_RANGE_RIDER** | +₹18,695 (83.7% WR) | **+₹28K** (88% WR) | Entry 12:30 cutoff, wider TSL |
| **MAGIC_SQUARE** | +₹17,124 (76.8% WR) | **+₹25K** (82% WR) | Faster TSL 5%/3%, ₹100 min |
| **MEAN_REVERSION** | +₹6,560 (77.8% WR) | **+₹11K** (82% WR) | ADX 25, BB 2σ filter |

### 3. UNTESTED STRATEGIES (5) - Medium Priority
| Strategy | Status | DNA Ready | Potential |
|----------|--------|-----------|-----------|
| **GAMMA_BLAST** | Expiry only | ✅ | +₹15K |
| **ZERO_HERO** | Expiry OTM PE | ✅ | +₹20K |
| **AI_ENHANCED** | Multi-factor | ✅ | +₹10K |
| **BREAKOUT** | PE only | ✅ | +₹8K |
| **ULTIMATE_DHL** | Fixed filters | ✅ | +₹20K |

---

## 🔧 DETAILED DNA SETTINGS

### === FIXED STRATEGIES ===

#### 1. TREND_FOLLOWING (COMPLETELY REWORKED)

**PROBLEM**: 66% TIME exits, 33% WR, losing ₹1,602  
**ROOT CAUSE**: Entering too late, no trend confirmation  
**SOLUTION**: Complete DNA overhaul

```python
TREND_FOLLOWING DNA:
├── TIMING
│   ├── entry_start: 945      # 9:45 - earliest possible
│   ├── entry_cutoff: 1130    # 11:30 - NO LATE ENTRIES
│   └── max_trades_per_day: 2
│
├── EXITS (Tightened for quick moves)
│   ├── tsl_activate: 0.05    # 5% (lower = earlier arm)
│   ├── tsl_trail: 0.03      # 3% (tighter = faster lock)
│   ├── target_pct: 0.25      # 25% (faster exits)
│   └── sl_backstop: 0.25     # 25% (tighter stop)
│
├── FILTERS (Strict)
│   ├── min_confidence: 0.88  # High threshold
│   ├── volume_spike: 1.4      # Strong volume required
│   ├── ema_required: True    # 9>21>50 or 9<21<50
│   └── direction: BOTH        # Changed from PE only
│
├── PREMIUM
│   ├── min_premium: 60
│   └── max_premium: 500
│
├── INDEX
│   ├── allowed: NIFTY, BANKNIFTY, FINNIFTY, SENSEX
│   └── blocked_regimes: HIGH_VOLATILITY
│
└── EXPECTED RESULT
    ├── Win Rate: 70-75% (up from 33%)
    ├── Trades: ~40 (vs 3 before)
    └── Profit: +₹5K-8K (vs -₹1,602)
```

#### 2. SHORT_UNWIND_V2 (PCR REPLACED)

**PROBLEM**: 86% TIME exits, 40% WR, PCR unreliable  
**ROOT CAUSE**: PCR signal quality poor in 15min data  
**SOLUTION**: Replace PCR with Volume + OI detection

```python
SHORT_UNWIND_V2 DNA:
├── TIMING (Afternoon focus)
│   ├── entry_start: 1230     # 12:30 - post-lunch
│   ├── entry_cutoff: 1400    # 14:00 - before EOD rush
│   └── max_trades_per_day: 2
│
├── EXITS (Quick profit take)
│   ├── tsl_activate: 0.06     # 6%
│   ├── tsl_trail: 0.04       # 4%
│   ├── target_pct: 0.30      # 30% (quick target)
│   └── sl_backstop: 0.20     # 20% (tight)
│
├── FILTERS (Volume-based)
│   ├── min_confidence: 0.85
│   ├── volume_spike: 1.5      # HIGH volume = conviction
│   ├── ema_required: True     # Price above EMAs
│   └── direction: CE          # Long only
│
├── SIGNAL (NEW - Replaces PCR)
│   ├── Old: PCR < 0.85
│   └── New: Volume 1.5x + OI drop + Green candle
│
├── PREMIUM
│   ├── min_premium: 80        # Higher to cover fees
│   └── max_premium: 400
│
├── INDEX
│   ├── allowed: NIFTY, BANKNIFTY, FINNIFTY
│   └── blocked_regimes: TRENDING_BEAR  # Don't fight
│
└── EXPECTED RESULT
    ├── Win Rate: 65-70% (up from 40%)
    ├── Trades: ~20-25
    └── Profit: +₹5K-8K (vs -₹1,605)
```

#### 3. ORDER_BLOCK_REVERSAL (ALREADY WORKING)

**STATUS**: Fixed! 81% WR, +₹3,721  
**KEEP CURRENT DNA**:

```python
ORDER_BLOCK_REVERSAL DNA:
├── TIMING (Fixed from 13:00 to 12:15)
│   ├── entry_start: 1000
│   ├── entry_cutoff: 1215     # KEY FIX!
│   └── max_trades_per_day: 4
│
├── EXITS
│   ├── tsl_activate: 0.10
│   ├── tsl_trail: 0.08
│   ├── target_pct: 0.60
│   └── sl_backstop: 0.35
│
├── FILTERS
│   ├── volume_spike: 1.3       # Reversal needs volume
│   └── min_confidence: 0.84
│
└── RESULT: KEEP AS-IS (81% WR)
```

---

### === OPTIMIZED STRATEGIES ===

#### 4. WIDE_RANGE_RIDER (REDUCE TIME EXITS)

**CURRENT**: +₹18,695, 83.7% WR, 14% TIME exits  
**TARGET**: +₹28K, 88% WR, <8% TIME exits

```python
WIDE_RANGE_RIDER DNA OPTIMIZED:
├── TIMING
│   ├── entry_start: 945
│   └── entry_cutoff: 1230     # CHANGED from 13:00
│
├── EXITS (Wider TSL)
│   ├── tsl_activate: 0.07     # 7% (lower = earlier)
│   ├── tsl_trail: 0.05        # 5% (wider = more room)
│   ├── target_pct: 0.50
│   └── sl_backstop: 0.30
│
├── FILTERS
│   ├── volume_spike: 1.2
│   └── vwap_confirmation: True  # Re-add VWAP
│
└── EXPECTED: +₹28K, 88% WR
```

#### 5. MAGIC_SQUARE (FASTER EXITS)

**CURRENT**: +₹17,124, 76.8% WR, 23% TIME exits  
**TARGET**: +₹25K, 82% WR, <15% TIME exits

```python
MAGIC_SQUARE DNA OPTIMIZED:
├── TIMING
│   ├── entry_start: 1030      # Magic levels window
│   └── entry_cutoff: 1430
│
├── EXITS (FASTER - Brokerage death fix)
│   ├── tsl_activate: 0.05      # 5% (earlier)
│   ├── tsl_trail: 0.03        # 3% (tighter)
│   ├── target_pct: 0.20        # 20% (LOWER = quick exits)
│   └── sl_backstop: 0.20      # 20% (tight)
│
├── PREMIUM (Higher min)
│   ├── min_premium: 100       # CHANGED from 80
│   └── max_premium: 400
│
└── EXPECTED: +₹25K, 82% WR
```

#### 6. MEAN_REVERSION (TIGHTER ADX)

**CURRENT**: +₹6,560, 77.8% WR, 22% TIME exits  
**TARGET**: +₹11K, 82% WR, <15% TIME exits

```python
MEAN_REVERSION DNA OPTIMIZED:
├── TIMING
│   ├── entry_start: 945
│   └── entry_cutoff: 1300
│
├── EXITS
│   ├── tsl_activate: 0.06
│   ├── tsl_trail: 0.04
│   ├── target_pct: 0.35
│   └── sl_backstop: 0.30
│
├── FILTERS (Tighter)
│   ├── adx_max: 25.0           # CHANGED from 28
│   ├── bb_position: 2.0σ       # Require BB extension
│   └── volume_spike: 1.3
│
└── EXPECTED: +₹11K, 82% WR
```

---

### === UNTESTED STRATEGIES ===

#### 7. GAMMA_BLAST (EXPIRY ONLY)

```python
GAMMA_BLAST DNA:
├── TIMING (Expiry only!)
│   ├── entry_start: 1330      # Last 2 hours
│   └── entry_cutoff: 1430
│
├── EXITS (Aggressive)
│   ├── tsl_activate: 0.08
│   ├── tsl_trail: 0.06
│   └── target_pct: 0.70        # 2x normal (70%)
│
├── FILTERS
│   ├── is_expiry: True         # ONLY ON EXPIRY
│   └── volume_spike: 1.5       # High volume required
│
├── PREMIUM (Cheap OTM)
│   ├── min_premium: 30
│   └── max_premium: 200
│
└── POTENTIAL: +₹15K on expiry days
```

#### 8. ZERO_HERO (EXPIRY OTM)

```python
ZERO_HERO DNA:
├── TIMING (Expiry only!)
│   ├── entry_start: 1300
│   └── entry_cutoff: 1430
│
├── EXITS (Hero or Zero)
│   ├── tsl_activate: 0.10
│   ├── tsl_trail: 0.08
│   └── target_pct: 1.00        # 100% target!
│
├── DIRECTION
│   └── direction: PE            # Put only (downside gamma)
│
├── PREMIUM (Very cheap OTM)
│   ├── min_premium: 20
│   └── max_premium: 50
│
└── POTENTIAL: +₹20K (high risk/reward)
```

#### 9. AI_ENHANCED (MULTI-FACTOR)

```python
AI_ENHANCED DNA:
├── TIMING
│   ├── entry_start: 945
│   └── entry_cutoff: 1430
│
├── EXITS
│   ├── tsl_activate: 0.08
│   ├── tsl_trail: 0.06
│   └── target_pct: 0.50
│
├── FILTERS (AI Calibrated)
│   ├── pcr_calibrated: 1.33     # Not raw PCR
│   ├── min_confidence: 0.88     # High AI confidence
│   └── multi_factor: True       # Ensemble of signals
│
└── POTENTIAL: +₹10K
```

#### 10. BREAKOUT (VOLUME CONFIRMED)

```python
BREAKOUT DNA:
├── TIMING
│   ├── entry_start: 945
│   └── entry_cutoff: 1400
│
├── DIRECTION
│   └── direction: PE            # Start with PE only
│
├── EXITS
│   ├── tsl_activate: 0.10
│   ├── tsl_trail: 0.08
│   └── target_pct: 0.50
│
├── FILTERS
│   └── volume_spike: 1.4        # Breakout needs volume
│
└── POTENTIAL: +₹8K
```

#### 11. ULTIMATE_DHL (FIXED FILTERS)

```python
ULTIMATE_DAY_HIGH_LOW DNA:
├── TIMING
│   ├── entry_start: 1000
│   └── entry_cutoff: 1430
│
├── EXITS
│   ├── tsl_activate: 0.08
│   ├── tsl_trail: 0.06
│   └── target_pct: 0.50
│
├── FILTERS (Fixed)
│   ├── volume_spike: 1.5        # High volume
│   └── regime_blocked: {TRENDING_BULL, TRENDING_BEAR}
│
└── POTENTIAL: +₹20K
```

---

## 📊 INDEX-SPECIFIC ADJUSTMENTS

All DNA settings above are for NIFTY (baseline). Apply these multipliers for other indices:

```python
INDEX_TSL_MULTIPLIERS = {
    'NIFTY':      {'activate': 1.0, 'trail': 1.0, 'target': 1.0},  # Baseline
    'BANKNIFTY':  {'activate': 1.3, 'trail': 1.3, 'target': 1.2},  # 30% more room
    'FINNIFTY':   {'activate': 1.2, 'trail': 1.2, 'target': 1.1},  # 20% more room
    'SENSEX':     {'activate': 1.4, 'trail': 1.4, 'target': 1.3},  # 40% more room
}

Example: BANKNIFTY TSL
  NIFTY: tsl_activate=0.06 → BANKNIFTY: 0.06 × 1.3 = 0.078 (capped at 0.20)
```

---

## 💰 TOTAL IMPROVEMENT PROJECTION

### Current State (After Fixes):
- Total PnL: ₹102,357
- Win Rate: 80.8%
- Trades: 678

### After Implementing OPTIMIZED DNA (Phase 2):
| Strategy | Current | Optimized | Gain |
|----------|---------|-----------|------|
| WIDE_RANGE_RIDER | ₹18,695 | ₹28,000 | +₹9,305 |
| MAGIC_SQUARE | ₹17,124 | ₹25,000 | +₹7,876 |
| MEAN_REVERSION | ₹6,560 | ₹11,000 | +₹4,440 |
| **Subtotal** | **₹42,379** | **₹64,000** | **+₹21,621** |

### After Adding UNTESTED (Phase 3):
| Strategy | Potential |
|----------|-----------|
| GAMMA_BLAST | +₹15,000 |
| ZERO_HERO | +₹20,000 |
| AI_ENHANCED | +₹10,000 |
| BREAKOUT | +₹8,000 |
| ULTIMATE_DHL | +₹20,000 |
| **Subtotal** | **+₹73,000** |

### GRAND TOTAL PROJECTION:
```
Current:              ₹102,357
+ Optimized (3):     +₹21,621
+ Untested (5):      +₹73,000
─────────────────────────────
TOTAL POTENTIAL:     ₹196,978

Win Rate: 80.8% → 84-85%
Trades: 678 → ~850-900
```

---

## 🚀 IMPLEMENTATION ROADMAP

### WEEK 1: Deploy Fixed DNA
1. ✅ TREND_FOLLOWING (9:45-11:30, tight TSL)
2. ✅ SHORT_UNWIND_V2 (Volume-based, afternoon)
3. ✅ ORDER_BLOCK_REVERSAL (keep as-is)

**Expected**: ₹102K → ₹110K

### WEEK 2-3: Optimize Top 3
1. 🔄 WIDE_RANGE_RIDER (12:30 cutoff)
2. 🔄 MAGIC_SQUARE (faster TSL)
3. 🔄 MEAN_REVERSION (tighter ADX)

**Expected**: ₹110K → ₹132K

### MONTH 2: Test Untested 5
1. 🧪 GAMMA_BLAST (expiry testing)
2. 🧪 ZERO_HERO (expiry testing)
3. 🧪 AI_ENHANCED (validation)
4. 🧪 BREAKOUT (PE only test)
5. 🧪 ULTIMATE_DHL (volume filter test)

**Expected**: ₹132K → ₹160K+

---

## 📁 FILES

| File | Purpose |
|------|---------|
| `STRATEGY_DNA_FIXES_20260606.py` | Complete DNA configurations |
| `DNA_IMPLEMENTATION_GUIDE_20260606.md` | This guide |

---

**Ready to implement in BACKTEST_V7_AGGRESSIVE.py**
