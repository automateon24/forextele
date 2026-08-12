# 🏛️ Grok Risk Model — Concurrent Multi-Asset Portfolio Backtest Report
## Full Portfolio Backtest Across All 8 Assets ($1,500 Loaded Capital)

- **Initial Capital**: $1,500.00 USD
- **Final Balance**: **$476.51 USD**
- **Net Return**: **-68.23%** ($-1,023.49 USD)
- **Total Trades Taken**: 140 trades
- **Win Rate**: **33.57%**
- **Profit Factor**: **0.51**
- **Max Account Drawdown**: **68.23%** ($1,023.49 USD)

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
| **GOLD** | 96 | 46.88% | $-470.34 | 0.70 |
| **SILVER** | 4 | 0.00% | $-186.32 | 0.00 |
| **EURUSD** | 5 | 0.00% | $-100.70 | 0.00 |
| **GBPUSD** | 3 | 0.00% | $-60.42 | 0.00 |
| **USDJPY** | 28 | 7.14% | $-125.15 | 0.02 |
| **AUDUSD** | 2 | 0.00% | $-40.28 | 0.00 |
| **NZDUSD** | 2 | 0.00% | $-40.28 | 0.00 |
