# 🏛️ Grok Risk Model — Concurrent Multi-Asset Portfolio Backtest Report
## Full Portfolio Backtest Across All 8 Assets ($1,500 Loaded Capital)

- **Initial Capital**: $1,500.00 USD
- **Final Balance**: **$850.50 USD**
- **Net Return**: **-43.30%** ($-649.50 USD)
- **Total Trades Taken**: 292 trades
- **Win Rate**: **46.23%**
- **Profit Factor**: **0.55**
- **Max Account Drawdown**: **48.19%** ($768.66 USD)

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
| **GOLD** | 48 | 29.17% | $-301.26 | 0.52 |
| **SILVER** | 74 | 48.65% | $-122.21 | 0.69 |
| **EURUSD** | 37 | 37.84% | $-78.60 | 0.32 |
| **GBPUSD** | 44 | 47.73% | $-58.54 | 0.57 |
| **USDJPY** | 73 | 58.90% | $-61.38 | 0.47 |
| **USDCHF** | 3 | 100.00% | $+6.14 | 99.00 |
| **AUDUSD** | 5 | 40.00% | $-15.60 | 0.15 |
| **NZDUSD** | 8 | 25.00% | $-18.05 | 0.20 |
