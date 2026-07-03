# COMPLETE STRATEGY DNA GUIDE
## 25 Strategies + 10 New | NIFTY Options Trading System

**Version:** 7.0 | **Date:** June 6, 2026 | **Capital:** Rs. 4L | **Lots:** 2 max

---

## SYSTEM CONFIGURATION

### Performance Summary
- **Total Trades:** 591
- **Win Rate:** 82.1%
- **Total PnL:** Rs. +174,966
- **Daily Average:** Rs. 1,548 (0.39%)
- **Max Drawdown:** Rs. -15,501
- **Green Days:** 76/113 (67.3%)

### Tiered Entry Cutoff System
| Tier | Cutoff | Strategies | Rationale |
|------|--------|------------|-----------|
| 1 | 11:00 | Trend followers, Day High/Low | High conviction, avoid TIME exits |
| 2 | 12:30 | Reversal strategies | Proven performers, moderate window |
| 3 | 13:00 | Volume-based, new strategies | Need afternoon volatility |

### Index Multipliers
| Index | TSL Activate | TSL Trail | Target |
|-------|--------------|-----------|--------|
| NIFTY | 1.0x | 1.0x | 1.0x |
| BANKNIFTY | 1.3x | 1.3x | 1.2x |
| FINNIFTY | 1.2x | 1.2x | 1.1x |
| SENSEX | 1.4x | 1.4x | 1.3x |

---

## TIER 1: LOCKED CORE STRATEGIES (8) - DO NOT MODIFY

### 1. DAY_LOW_BULLISH
**Philosophy:** Buy CE at day low with volume confirmation  
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.60, sl=0.35, thresh=0.80, max_d=5, min_p=50, max_p=500  
**Entry:** Day low touch + volume >1.3x, cutoff 11:00  
**Exit:** TSL 10%/8%, hard stop 35%, target 60%  
**Performance:** 32 trades, 94% WR, +Rs.9,670  
**Status:** LOCKED

### 2. DAY_HIGH_BEARISH
**Philosophy:** Buy PE at day high, skip TRENDING_BULL regime  
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.60, sl=0.35, thresh=0.82, max_d=3, min_p=50, max_p=500  
**Entry:** Day high touch + volume >1.3x, regime gate, cutoff 11:00  
**Exit:** TSL 10%/8%, hard stop 35%, target 60%  
**Performance:** 12 trades, 83% WR, +Rs.7,270  
**Status:** LOCKED

### 3. MEAN_REVERSION
**Philosophy:** Fade extremes using BB + ADX filter  
**DNA:** tsl_a=0.06, tsl_t=0.04, tgt=0.35, sl=0.30, thresh=0.82, max_d=4, min_p=45, max_p=600  
**Entry:** Price >1.8 BB bands, ADX <28 (ranging), cutoff 12:30  
**Exit:** TSL 6%/4%, hard stop 30%, target 35%  
**Performance:** 22 trades, 73% WR, +Rs.9,696  
**Status:** LOCKED

### 4. VOLATILITY_BREAKOUT
**Philosophy:** Capture explosive moves on high volatility  
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.70, sl=0.35, thresh=0.85, max_d=4, min_p=60, max_p=700  
**Entry:** BB width >2x, volume >2x, cutoff 12:30  
**Exit:** TSL 10%/8%, hard stop 35%, target 70%  
**Performance:** 2 trades, 100% WR, +Rs.13,768  
**Status:** LOCKED

### 5. EARLY_BREAKDOWN
**Philosophy:** First breakdown capture for max premium decay  
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.60, sl=0.35, thresh=0.90, max_d=2, min_p=40, max_p=400  
**Entry:** First 30min breakdown, volume >1.5x, cutoff 11:00  
**Exit:** TSL 10%/8%, hard stop 35%, target 60%  
**Performance:** 6 trades, 100% WR, +Rs.8,846  
**Status:** LOCKED

### 6. BEAR_TREND_FOLLOWER
**Philosophy:** Follow bearish trends with EMA alignment  
**DNA:** tsl_a=0.12, tsl_t=0.10, tgt=0.80, sl=0.35, thresh=0.88, max_d=3, min_p=45, max_p=500  
**Entry:** Price < 9EMA < 21EMA, ADX >25, TRENDING_BEAR only, cutoff 11:00  
**Exit:** TSL 12%/10%, hard stop 35%, target 80%  
**Performance:** 32 trades, 88% WR, +Rs.10,514  
**Status:** LOCKED

### 7. BULL_TREND_FOLLOWER
**Philosophy:** Follow bullish trends with EMA alignment  
**DNA:** tsl_a=0.12, tsl_t=0.10, tgt=0.80, sl=0.35, thresh=0.88, max_d=3, min_p=45, max_p=500  
**Entry:** Price > 9EMA > 21EMA, ADX >25, TRENDING_BULL only, cutoff 11:00  
**Exit:** TSL 12%/10%, hard stop 35%, target 80%  
**Performance:** 20 trades, 100% WR, +Rs.10,279  
**Status:** LOCKED

### 8. ORDER_BLOCK_REVERSAL
**Philosophy:** Trade reversals from key order block levels  
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.60, sl=0.35, thresh=0.84, max_d=4, min_p=50, max_p=500  
**Entry:** Order block test, rejection pattern, volume >1.3x, cutoff 12:30  
**Exit:** TSL 10%/8%, hard stop 35%, target 60%  
**Performance:** 2 trades, 100% WR, +Rs.2,438  
**Status:** LOCKED

---

## TIER 2: REVIVAL STRATEGIES (4) - FIXED AND WORKING

### 9. WIDE_RANGE_RIDER
**Philosophy:** Capture large intraday range expansion  
**DNA:** tsl_a=0.07, tsl_t=0.05, tgt=0.50, sl=0.30, thresh=0.82, max_d=3, min_p=60, max_p=600  
**Entry:** Range > threshold (NIFTY 120pts, BN 300pts), volume >1.2x, cutoff 12:30  
**Performance:** 22 trades, 91% WR, +Rs.8,580  
**Status:** + GOOD

### 10. MAGIC_SQUARE
**Philosophy:** Exploit psychological levels (Gann squares)  
**DNA:** tsl_a=0.05, tsl_t=0.03, tgt=0.20, sl=0.20, thresh=0.85, max_d=3, min_p=100, max_p=400  
**Entry:** Strike at psychological level, premium >100 (fees), cutoff 12:30  
**Performance:** 82 trades, 71% WR, +Rs.14,076  
**Status:** + GOOD (high volume)

### 11. SHORT_UNWIND
**Philosophy:** Capture short covering (OI + volume based, NOT PCR)  
**DNA:** tsl_a=0.04, tsl_t=0.02, tgt=0.20, sl=0.15, thresh=0.90, max_d=1, min_p=100, max_p=350  
**Entry:** OI decreasing, volume >1.5x, NO PCR used, cutoff 10:15 (ultra strict)  
**Performance:** DISABLED - Always loses  
**Status:** ❌ DISABLED

### 12. ENHANCED_BEARISH
**Philosophy:** Advanced bearish patterns with multiple confirmations  
**DNA:** tsl_a=0.12, tsl_t=0.10, tgt=0.80, sl=0.35, thresh=0.75, max_d=3, min_p=50, max_p=500  
**Entry:** Bearish engulfing, volume >1.3x, RSI >60, cutoff 13:00  
**Performance:** 188 trades, 84% WR, +Rs.22,678  
**Status:** * TOP (highest volume)

---

## TIER 3: HIGH-REWARD STRATEGIES (3)

### 13. ULTIMATE_DAY_HIGH_LOW
**Philosophy:** Aggressive day high/low with moonshot targets  
**DNA:** tsl_a=0.15, tsl_t=0.12, tgt=1.00, sl=0.40, thresh=0.75, max_d=2, min_p=100, max_p=700  
**Entry:** Extreme levels, volume >2x, range >2x, cutoff 13:00  
**Performance:** 10 trades, 70% WR, +Rs.4,078  
**Status:** ~ OK (high risk/reward)

### 14. SCALPING
**Philosophy:** Rapid small profits with tight stops  
**DNA:** tsl_a=0.06, tsl_t=0.04, tgt=0.25, sl=0.20, thresh=0.90, max_d=5, min_p=80, max_p=250  
**Entry:** 1min momentum, VWAP cross, volume >1.5x, cutoff 13:00  
**Status:** ~ OK (high frequency)

### 15. OPTIONS_GREEKS
**Philosophy:** Trade based on Greeks (Delta, Gamma, Theta, Vega)  
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.50, sl=0.30, thresh=0.85, max_d=3, min_p=70, max_p=500  
**Entry:** Delta >0.50, Gamma spike, Theta <2, cutoff 13:00  
**Status:** ~ OK (requires Greeks data)

---

## TIER 4: ADVANCED STRATEGIES (9)

### 16. AI_ENHANCED
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.60, sl=0.35, thresh=0.82, max_d=4, min_p=50, max_p=500  
**Entry:** ML pattern recognition, confidence >=0.82, cutoff 13:00

### 17. BREAKOUT
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.60, sl=0.35, thresh=0.85, max_d=3, min_p=40, max_p=400  
**Entry:** Classic breakout, volume >1.5x, close beyond level, cutoff 13:00

### 18. GAMMA_BLAST (Expiry Only)
**DNA:** tsl_a=0.15, tsl_t=0.12, tgt=2.00, sl=0.50, thresh=0.80, max_d=2, min_p=10, max_p=150  
**Entry:** EXPIRY ONLY, ATM/OTM, Gamma >0.05, volume explosion, cutoff 14:00

### 19. ZERO_HERO (Expiry Only)
**DNA:** tsl_a=0.12, tsl_t=0.10, tgt=1.00, sl=0.35, thresh=0.85, max_d=2, min_p=20, max_p=100  
**Entry:** EXPIRY ONLY, deep OTM cheap, high OI, cutoff 14:00

### 20. MORNING_BREAKOUT
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.60, sl=0.30, thresh=0.88, max_d=2, min_p=40, max_p=400  
**Entry:** Opening range breakout, first hour, cutoff 11:00

### 21. LONG_UNWIND
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.50, sl=0.30, thresh=0.82, max_d=3, min_p=50, max_p=400  
**Entry:** OI decreasing on long side, price falling, cutoff 13:00

### 22. PUT_WRITER_SUPPORT
**DNA:** tsl_a=0.08, tsl_t=0.06, tgt=0.40, sl=0.25, thresh=0.85, max_d=3, min_p=50, max_p=200  
**Entry:** Put writers active, support building, cutoff 13:00

### 23. RESIST_BREAK
**DNA:** tsl_a=0.08, tsl_t=0.06, tgt=0.50, sl=0.20, thresh=0.85, max_d=3, min_p=50, max_p=250  
**Entry:** Clean resistance break, volume confirmation, cutoff 13:00

### 24. DAY_HIGH_LOW_TRADITIONAL
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.60, sl=0.35, thresh=0.80, max_d=3, min_p=50, max_p=500  
**Entry:** Traditional day high/low without enhancements, cutoff 13:00

### 25. ENHANCED_BULLISH
**DNA:** tsl_a=0.10, tsl_t=0.08, tgt=0.60, sl=0.30, thresh=0.82, max_d=3, min_p=50, max_p=500  
**Entry:** Advanced bullish patterns, multiple confirmations, cutoff 13:00

---

## TIER 5: NEW UNTESTED STRATEGIES (10) - ADDED FOR POTENTIAL

### 26. MOMENTUM_BURST
**DNA:** tsl_a=0.06, tsl_t=0.04, tgt=0.40, sl=0.25, thresh=0.85, max_d=2, min_p=60, max_p=400

### 27. VWAP_BOUNCE
**DNA:** tsl_a=0.05, tsl_t=0.03, tgt=0.30, sl=0.20, thresh=0.87, max_d=2, min_p=70, max_p=350

### 28. OPENING_DRIVE
**DNA:** tsl_a=0.08, tsl_t=0.06, tgt=0.50, sl=0.30, thresh=0.88, max_d=2, min_p=50, max_p=400

### 29. PREMIUM_CRUSH
**DNA:** tsl_a=0.04, tsl_t=0.02, tgt=0.20, sl=0.15, thresh=0.86, max_d=3, min_p=90, max_p=300

### 30. RSI_REVERSAL
**DNA:** tsl_a=0.05, tsl_t=0.03, tgt=0.30, sl=0.20, thresh=0.85, max_d=2, min_p=60, max_p=400

### 31. EMA_CROSSOVER
**DNA:** tsl_a=0.07, tsl_t=0.05, tgt=0.45, sl=0.25, thresh=0.88, max_d=2, min_p=55, max_p=450

### 32. BOLLINGER_SQUEEZE
**DNA:** tsl_a=0.06, tsl_t=0.04, tgt=0.40, sl=0.25, thresh=0.87, max_d=2, min_p=65, max_p=400

### 33. VOLUME_CLIMAX
**DNA:** tsl_a=0.05, tsl_t=0.03, tgt=0.35, sl=0.20, thresh=0.89, max_d=2, min_p=70, max_p=350

### 34. ATR_BREAK
**DNA:** tsl_a=0.08, tsl_t=0.06, tgt=0.55, sl=0.30, thresh=0.86, max_d=2, min_p=50, max_p=500

### 35. MACD_DIVERGENCE
**DNA:** tsl_a=0.06, tsl_t=0.04, tgt=0.40, sl=0.25, thresh=0.87, max_d=2, min_p=60, max_p=400

---

## DISABLED STRATEGIES (2)

### TREND_FOLLOWING
**Reason:** 66% TIME exits, always loses even with fixes  
**Previous:** 33% WR, -Rs.1,602

### SHORT_UNWIND (Original PCR-based)
**Reason:** 87% TIME exits, PCR data unreliable  
**Previous:** 40% WR, -Rs.1,605

---

## ENTRY FILTERS SUMMARY

| Filter | Applies To | Condition |
|--------|------------|-----------|
| Volume Spike | Reversal strategies | >1.3x average |
| ADX Filter | Mean Reversion | ADX <28 (ranging) |
| EMA Alignment | Trend followers | 9EMA > 21EMA (bull) or < (bear) |
| Regime Gate | Day High Bearish | Skip TRENDING_BULL |
| Min Premium | Magic Square | >Rs.80 (fees) |
| PCR Stability | Short Unwind | 3-cycle stability (DISABLED) |

---

## EXIT LOGIC

### Trailing Stop Loss (TSL)
1. Activate when profit reaches `tsl_a`%
2. Trail at `tsl_t`% below highest price
3. Exit if price drops to trail level

### Hard Stop Loss
- Exit immediately if loss reaches `sl`%

### Fixed Target
- Exit when profit reaches `tgt`%

### TIME Exit
- Force exit at 14:30 if still in trade
- Major cause of losses - minimized by early cutoffs

---

## RISK MANAGEMENT

### Per Trade
- Max 2 lots per trade
- Max 2 entries per strategy per day
- Brokerage: Rs.50 per round trip

### Per Day
- No daily loss limit (yet)
- Max 15 total trades across all strategies

### Drawdown Control
- Current: Rs.15,501 (3.9% of capital)
- Target: <Rs.20,000 (5%)

---

## FILES REFERENCE

| File | Purpose |
|------|---------|
| BACKTEST_V7_AGGRESSIVE.py | Main backtest engine |
| FINAL_25_STRATEGIES_REPORT_2LOTS.json | Complete performance data |
| backtest_results/v7_multiindex_trades.csv | All 591 trades |
| STRATEGY_DNA_GUIDE.md | This documentation |

---

## BACKUP INSTRUCTIONS

To backup this system:
1. Copy BACKTEST_V7_AGGRESSIVE.py
2. Copy STRATEGY_DNA_GUIDE.md
3. Copy FINAL_25_STRATEGIES_REPORT_2LOTS.json
4. Copy backtest_results/ folder
5. Store in backup_YYYY-MM-DD/ folder

---

*Generated: June 6, 2026 | System Version: 7.0 | Total Strategies: 35 (33 active + 2 disabled)*
