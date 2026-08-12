# 🏛️ Grok Risk Model — Concurrent Multi-Asset Portfolio Backtest Report
## Full Portfolio Backtest Across All 8 Assets ($1,500 Loaded Capital)

- **Initial Capital**: $1,500.00 USD
- **Final Balance**: **$1,262.13 USD**
- **Net Return**: **-15.86%** ($-237.87 USD)
- **Total Trades Taken**: 111 trades
- **Win Rate**: **53.15%**
- **Profit Factor**: **0.86**
- **Max Account Drawdown**: **24.25%** ($404.03 USD)

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
| **GOLD** | 111 | 53.15% | $-237.87 | 0.86 |
