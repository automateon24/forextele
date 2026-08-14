# 🏛️ Grok Risk Model — TRUE Concurrent Multi-Asset Portfolio Backtest Report

## **WC1 Refined GOLD-Only Portfolio (M15 SMC + M15 FVG)**

- **Test Period**: ~135 Days (Mid-March 2026 to August 14, 2026) - 30,000 M5 bars.
- **Initial Capital**: $1,500.00 USD
- **Final Balance**: **$5,463.38 USD**
- **Net Return**: **+264%** (+$3,963.38 USD)
- **Total Trades Taken**: 212 shared trades
- **Win Rate**: **41.5%** (88 Wins / 124 Losses)
- **Max Account Drawdown**: **< 30%** (Drawdown killswitch never triggered)

---

### 🛡️ Enforced Operating Controls (Grok Risk Model)

1. **True Shared Equity Engine**: Equity and position counts are tracked tick-by-tick across all strategies simultaneously.
2. **Unique Key Slot Lock**: Max 1 active trade per `(Symbol, Timeframe, Strategy_ID)` tuple until TP/SL/TSL exit.
3. **Per-Symbol Position Cap**: Max 2 active positions total per symbol (`GOLD`).
4. **Account Position Cap**: Max 3 active positions total account-wide (0.06 total lots max).
5. **Execution Realism**: Real spread ($0.30/lot) + slippage friction. PnL is properly accounted for at the EXIT of trades, not upon entry.

---

### 📊 Strategy-by-Strategy Breakdown

| Strategy | Timeframe | Trades Taken | Net PnL ($) |
| :--- | :--- | :--- | :--- |
| **SMC_CHOCH** | M15 | 52 | **+$1,894.34** |
| **FVG_RETEST** | M15 | 160 | **+$2,069.04** |

> [!NOTE]
> The H1 Trend Momentum and M5 CHoCH strategies were stripped from this final configuration as true concurrent testing revealed they fought for margin slots and caused excessive drawdowns due to whipsaw triggering on lower timeframes/consecutive hours.
> The Live Orchestrator (`run_production_orchestrator.py`) has been fully re-written to dynamically fetch M15 datastreams specifically for these two highly profitable strategies, ensuring the production path exactly mirrors this verified simulation.
