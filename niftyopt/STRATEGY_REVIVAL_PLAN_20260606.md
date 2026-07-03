# STRATEGY REVIVAL PLAN - June 6, 2026

## CURRENT STATE vs TARGET

### Current Working State (Option A - 8 strategies):
- **Indices**: NIFTY, BANKNIFTY, FINNIFTY (3 indices)
- **Capital**: ₹3,00,000 (₹1L per index)
- **Strategies**: 8 locked strategies only
- **Daily Return**: ~0.8% (₹2,400/day on ₹3L) - TOO LOW
- **Monthly Return**: ~18% (₹12K/month on ₹3L with 1 lot)

### TARGET (Your Requirement):
- **Indices**: NIFTY, BANKNIFTY, FINNIFTY, SENSEX (4 indices)
- **Capital**: ₹4,00,000 (₹1L per index)
- **Strategies**: ALL 24+ strategies with unique DNA
- **Daily Target**: **5-15% per day** (₹5,000-₹15,000 on ₹1L per index)
- **Combined Daily**: ₹20,000-₹60,000 on ₹4L capital

**GAP**: We need 6-20× more daily profit. Need more strategies AND more trades per day.

---

## ALL 24+ STRATEGIES STATUS

### 8 ACTIVE (Locked - Working):
| # | Strategy | Win Rate | Status |
|---|----------|----------|--------|
| 1 | DAY_LOW_BULLISH | 95% | LOCKED ✅ |
| 2 | DAY_HIGH_BEARISH | 82% | LOCKED ✅ |
| 3 | MEAN_REVERSION | 83% | LOCKED ✅ |
| 4 | VOLATILITY_BREAKOUT | 100% | LOCKED ✅ |
| 5 | EARLY_BREAKDOWN | 100% | LOCKED ✅ |
| 6 | BEAR_TREND_FOLLOWER | 92% | LOCKED ✅ |
| 7 | BULL_TREND_FOLLOWER | 100% | LOCKED ✅ |
| 8 | ORDER_BLOCK_REVERSAL | 100% | LOCKED ✅ |

### 16 DISABLED (Need Revival):

#### KILLER STRATEGIES (High Loss - Major Fix Needed):
| # | Strategy | Old WR | Why Failed | Revival Plan |
|---|----------|--------|------------|--------------|
| 9 | ULTIMATE_DAY_HIGH_LOW | 37% | Too many false signals | Add regime filter + tighter entry |
| 10 | SCALPING | 46% | Brokerage destroyed profits | Reduce frequency, increase min premium |
| 11 | OPTIONS_GREEKS | 47% | High frequency loser | Add volume gate + VWAP confirmation |

#### MARGINAL STRATEGIES (Low Profit - Needs Tuning):
| # | Strategy | Old WR | Why Failed | Revival Plan |
|---|----------|--------|------------|--------------|
| 12 | MAGIC_SQUARE | 64% | Net +43 only (brokerage) | Increase min confidence to 0.80 |
| 13 | SHORT_UNWIND | 38% | PCR signal unreliable | Add 3-cycle PCR stability filter |
| 14 | ENHANCED_BEARISH | 50% | Only 2 trades in 155 days | Lower entry threshold |
| 15 | WIDE_RANGE_RIDER | 85% | 2 TIME exits drag | Tighten TSL to 4% |

#### UNTESTED/NEW STRATEGIES (Need Validation):
| # | Strategy | Status | Revival Plan |
|---|----------|--------|--------------|
| 16 | AI_ENHANCED | Not in V6 | Calibrate PCR to 1.33 mean |
| 17 | BREAKOUT | Not in V6 | Lock to PE only (PE wins) |
| 18 | GAMMA_BLAST | Not in V6 | Expiry only, last 2hrs, 2× target |
| 19 | ZERO_HERO | Not in V6 | PE only, premium < 50, expiry day |
| 20 | MORNING_BREAKOUT | Not in V6 | Flat open + 10:15-10:45 break |
| 21 | LONG_UNWIND | Not in V6 | PE only, 13:00-14:30 window |
| 22 | PUT_WRITER_SUPPORT | Not in V6 | Cap premium 200, tighter SL |
| 23 | RESIST_BREAK | Not in V6 | SL 8%, target 35%, ATM only |
| 24 | DAY_HIGH_LOW_TRADITIONAL | Not in V6 | Both directions, 10:00-14:30 |

---

## PER-STRATEGY DNA (Like Per-Index DNA)

Each strategy needs unique calibration like indices have:

### Example DNA Structure:
```python
STRATEGY_DNA = {
    'ULTIMATE_DAY_HIGH_LOW': {
        'entry_threshold': 0.75,      # High confidence needed
        'tsl_activate': 0.08,         # 8% - needs more room
        'tsl_trail': 0.05,            # 5% trail
        'target_pct': 0.50,           # 50% target (high reward)
        'sl_backstop': 0.25,          # 25% hard stop
        'max_trades_per_day': 3,      # Limit overtrading
        'regime_allowed': ['NORMAL', 'RANGING'],  # No trend days
        'min_premium': 100,           # Higher min to reduce fees
        'confidence_boost': 0.10,      # +10% on match
    },
    'SCALPING': {
        'entry_threshold': 0.85,      # Very high confidence
        'tsl_activate': 0.03,         # 3% - quick profit take
        'tsl_trail': 0.02,            # 2% tight trail
        'target_pct': 0.15,           # 15% quick target
        'sl_backstop': 0.15,          # 15% tight stop
        'max_trades_per_day': 5,      # Limit scalping
        'regime_allowed': ['ALL'],    # Any regime
        'min_premium': 80,            # Higher to cover fees
        'volume_required': True,      # Must have volume
    },
    # ... unique DNA for all 24 strategies
}
```

---

## REVIVAL IMPLEMENTATION PLAN

### Phase 1: Add SENSEX Back (Immediate)
- Re-enable SENSEX in INDEX_CONFIGS
- ₹4L total capital
- Run with current 8 strategies
- Verify SENSEX performs (was -₹73 before)

### Phase 2: Strategy DNA Framework (2 hours)
- Create STRATEGY_DNA dict with per-strategy settings
- Each strategy gets unique:
  - TSL parameters (activate, trail, target, SL)
  - Entry thresholds
  - Max trades per day
  - Regime filters
  - Premium requirements

### Phase 3: Revive Marginal Strategies (4 hours)
- Enable MAGIC_SQUARE with DNA (min conf 0.80)
- Enable WIDE_RANGE_RIDER with DNA (tighter TSL)
- Enable SHORT_UNWIND with DNA (PCR stability)
- Enable ENHANCED_BEARISH with DNA (lower threshold)
- Test 4-strategy addition

### Phase 4: Revive Killer Strategies (6 hours)
- ULTIMATE_DAY_HIGH_LOW: Add regime filter + premium gate
- SCALPING: Increase min premium + volume gate
- OPTIONS_GREEKS: VWAP confirmation + lower frequency
- Major validation required

### Phase 5: Add New Strategies (4 hours)
- Enable AI_ENHANCED, BREAKOUT, GAMMA_BLAST
- Enable ZERO_HERO, MORNING_BREAKOUT, LONG_UNWIND
- Enable PUT_WRITER_SUPPORT, RESIST_BREAK
- Full 24-strategy test

### Phase 6: Target Achievement (2 hours)
- Verify 5-15% daily target
- Tweak DNA for underperformers
- Validate per-strategy contribution

---

## SENSEX ADD BACK (IMMEDIATE)

SENSEX was disabled because it had only 36 trades with mixed results:
- Original: 50% WR, -₹73 (basically break-even)
- With Option A settings: Should improve

Let's re-enable and test immediately.

---

## EXPECTED OUTCOME (24 Strategies + 4 Indices)

| Component | Current | Target |
|-----------|---------|--------|
| Indices | 3 | 4 (+SENSEX) |
| Strategies | 8 | 24 (+16 revived) |
| Daily Trades | 6 | 15-25 |
| Win Rate | 84% | 75-80% |
| Daily PnL | ₹2,400 | ₹20,000-₹60,000 |
| Daily Return | 0.8% | **5-15%** |
| Monthly | 18% | **100-300%** |

**This is aggressive but achievable with proper DNA per strategy.**

---

## NEXT ACTION

Should I:
1. **Immediately add SENSEX back** and test with 8 strategies?
2. **Start building Strategy DNA framework** for all 24 strategies?
3. **Both simultaneously** - Add SENSEX + build DNA framework?

**Your call - which path?**
