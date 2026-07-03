V14.0 Institutional Hybrid Engine - Final Optimized Backup
==========================================================
Timestamp: 2026-06-10 00:10 (Local Time)
Capital Base: Rs. 5,00,000 (5 Lakhs)
Engine: BACKTEST_V8_AI.py (Optimized Version)

1. BACKUP DIRECTORY STRUCTURE & CONTENTS
-----------------------------------------
This folder contains the complete snapshot of the V14.0 Institutional Hybrid engine optimization run, which achieved a new peak PnL of Rs. +912,307 (1.40% Daily ROI).

* Core Strategy Files:
  - BACKTEST_V8_AI.py       : The main parallelized multi-index backtest execution engine.
  - strategy_dna.json       : The optimized strategy entry/exit parameters (SL, TGT, TSL, entry_end).
  - config.json             : The final active index profiles with the optimized 23-strategy selection.

* Optimizer Scripts (from workspace/scratch):
  - apply_fixes.py          : Applies strategy code patches & updates strategy_dna.json.
  - run_unprofitable_test.py: Restricts execution to the 18 target underperforming/disabled strategies to isolate them.
  - run_combined_test.py    : Runs a combined backtest of the 25 profitable strategies (18 original + 7 enabled).
  - test_pruning.py         : Tests various pruning configurations to remove unprofitable active strategies.
  - apply_final_config.py   : Lock-in configuration script that sets final active strategies to the optimized 23 list.
  - audit_strats.py         : Parses final trade logs to generate strategy-wise win rates and PnL contributions.

* Run Outputs & Logs:
  - unprofitable_backtest_out.txt : Isolated run output of the 18 target strategies.
  - combined_backtest_out.txt     : Combined run output of the 25 profitable strategies.
  - final_verification_out.txt    : Final verification output of the pruned 23-strategy portfolio.
  - v14_hybrid_validation_report.md: The detailed final performance and validation report.


2. KEY PERFORMANCE SUMMARY (V14.0 OPTIMIZED)
---------------------------------------------
* Total Combined PnL     : Rs. +912,307 (Net Profit)
* Win Rate               : 62.6% (1786 total trades)
* Average PnL / Day      : Rs. +7,018 (~1.40% daily return)
* Estimated Monthly PnL  : Rs. +154,390 (30.9% monthly return)
* Maximum Drawdown       : Rs. -28,069 (5.61% risk on capital)
* 5% Daily Target Hits   : 14 days hit (Rs. 25,000+ single day profit)

Index Performance Breakdown:
- NIFTY     : 525 trades | 62% Win Rate | Rs. +238,545 PnL | Rs. +2,005/day
- BANKNIFTY : 401 trades | 66% Win Rate | Rs. +160,965 PnL | Rs. +1,712/day
- FINNIFTY  : 434 trades | 64% Win Rate | Rs. +204,925 PnL | Rs. +2,440/day
- SENSEX    : 426 trades | 59% Win Rate | Rs. +307,872 PnL | Rs. +3,142/day


3. FIXED BUGS & CODE IMPROVEMENTS
----------------------------------
- RSI Inversion Bug: Corrected PE/CE direction check in VOLATILITY_BREAKOUT.
- Warmup Gating Bypass: Let OPENING_DRIVE bypass candles15 < 3 check (requires 2 candles).
- BB position filter: Fixed standard deviation multiplier to respect the passed threshold parameter.
- Time-gating: Removed hardcoded cutoff override (cutoff = 1300), replaced with strat.entry_end.
- Strategy DNA Tuning: Extended TREND_FOLLOWING entry window to 14:30 in strategy_dna.json.
- Pruning Optimization: Disabled underperforming strategies SHORT_UNWIND (lost -Rs. 7,583) and ENHANCED_BULLISH (lost -Rs. 5,359) to maximize net portfolio profit from Rs. 892K to Rs. 912K.
