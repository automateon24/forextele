# 🏛️ Grok Risk Model — Concurrent Multi-Asset Portfolio Backtest Report
## Full Portfolio Backtest Across All 8 Assets ($1,500 Loaded Capital)

- **Initial Capital**: $1,500.00 USD
- **Final Balance**: **$965.32 USD**
- **Net Return**: **-35.65%** ($-534.68 USD)
- **Total Trades Taken**: 47 trades
- **Win Rate**: **23.40%**
- **Profit Factor**: **0.23**
- **Max Account Drawdown**: **36.04%** ($543.20 USD)

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
| **GOLD** | 21 | 42.86% | $-221.66 | 0.40 |
| **SILVER** | 15 | 13.33% | $-174.87 | 0.04 |
| **EURUSD** | 2 | 0.00% | $-40.28 | 0.00 |
| **GBPUSD** | 2 | 0.00% | $-40.28 | 0.00 |
| **USDJPY** | 6 | 0.00% | $-37.45 | 0.00 |
| **NZDUSD** | 1 | 0.00% | $-20.14 | 0.00 |
