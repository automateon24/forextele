======================================================================
BACKUP: V8.3 AI FIXED 3 LOT OPTIONS ENGINE (PERCENTAGE REGIMES)
======================================================================
Date: 2026-06-06 21:05 (9:05 PM) [Updated with Regime Detector Fix]
Capital Base: Rs. 5,00,000
Lot Multiplier: Fixed 3 Lots for all trades (Nifty 225 shares, Finnifty 120 shares, Banknifty 45 shares, Sensex 30 shares)

Key Features:
- Resolved the absolute points bug in `regime_detector.py` by converting to percentage-based thresholds relative to day open.
- SENSEX trades unlocked: 125 trades (up from 8 trades).
- BANKNIFTY trades unlocked: 71 trades (up from 46 trades).
- Enabled 'ZERO_HERO' and 'GAMMA_BLAST' on all 4 active indices.
- Cutoff extended to 15:00 for expiry strategies to capture EOD moves.
- Adjusted trigger logic for ZERO_HERO and GAMMA_BLAST.
- Multi-index trade frequency: 444 trades with a 67.8% win rate.
- Realized PnL: Rs. +296,917 (Avg Rs. +3,227/day)
- Max Drawdown: Rs. -13,710 (2.7% of capital base)

Files included:
- BACKTEST_V8_AI.py: Main options engine script.
- regime_detector.py: Fixed percentage-based market regime detector.
- STRATEGY_DNA_GUIDE.md: Reference guide for base options strategies.
- v8_multiindex_trades.csv: The list of all 444 generated trades.
======================================================================
