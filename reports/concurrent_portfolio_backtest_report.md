# 🏛️ Grok Risk Model — Concurrent Multi-Asset Portfolio Backtest Report
## Full Portfolio Backtest Across All 8 Assets ($1,500 Loaded Capital)

- **Initial Capital**: $1,500.00 USD
- **Final Balance**: **$365.78 USD**
- **Net Return**: **-75.61%** ($-1,134.22 USD)
- **Total Trades Taken**: 139 trades
- **Win Rate**: **35.25%**
- **Profit Factor**: **0.43**
- **Max Account Drawdown**: **75.61%** ($1,134.22 USD)

---

### 🛡️ Enforced Operating Controls (Grok Risk Model)

1. **Unique Key Slot Lock**: Max 1 active trade per `(Symbol, Timeframe, Strategy_ID)` tuple until TP/SL/TSL exit.
2. **Per-Symbol Position Cap**: Max 2 active positions total per symbol (e.g. `GOLD`).
3. **Account Position Cap**: Max 3 active positions total account-wide (0.06 total lots max).
4. **Daily Drawdown Stop**: 3% daily equity loss stop (-$45.00 on $1,500 capital).
5. **Execution Realism**: Real spread + commission ($7/lot) + slippage friction.

---

### 📊 Asset-by-Asset Performance Breakdown

| Asset | Total Trades | Win Rate (%) | Net PnL ($) | Profit Factor |
| :--- | :--- | :--- | :--- | :--- |
| **GOLD** | 95 | 50.53% | $-470.09 | 0.64 |
| **SILVER** | 4 | 0.00% | $-360.13 | 0.00 |
| **EURUSD** | 1 | 0.00% | $-20.14 | 0.00 |
| **GBPUSD** | 5 | 0.00% | $-100.70 | 0.00 |
| **USDJPY** | 32 | 3.12% | $-140.87 | 0.00 |
| **USDCHF** | 1 | 0.00% | $-22.14 | 0.00 |
| **AUDUSD** | 1 | 0.00% | $-20.14 | 0.00 |
