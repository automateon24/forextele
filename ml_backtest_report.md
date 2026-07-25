# ML-Augmented Back-test Report

**Mode:** RAW (no ML model)

**Run date:** 2026-07-13 15:25:15

**Data source:** `backtest_1week_results.csv`

---

## 📊 Overall Summary

| Metric | Value |
|--------|-------|
| Total trades | 4,077 |
| Overall win-rate | 45.65% |
| Net P&L | $8,048.89 |
| Return on $10,000 capital | 80.49% |
| Average lot used | 0.0200 |
| Avg ML win-probability | 0.500 |
| Sharpe ratio (annualised) | 19.21 |
| Max draw-down | -0.80% |

---

## 📅 Daily ROI

| Date | P&L (USD) | Daily ROI % | Cumulative Capital |
|------|-----------|-------------|--------------------|
| 2026-07-07 | $1,413.79 | 14.14% | $11,413.79 |
| 2026-07-08 | $2,610.78 | 26.11% | $14,024.57 |
| 2026-07-09 | $1,551.61 | 15.52% | $15,576.18 |
| 2026-07-10 | $1,160.26 | 11.60% | $16,736.44 |
| 2026-07-11 | $-29.97 | -0.30% | $16,706.47 |
| 2026-07-12 | $-104.71 | -1.05% | $16,601.76 |
| 2026-07-13 | $1,447.13 | 14.47% | $18,048.89 |

---

## 🏆 Strategy Breakdown (Top 20)

| Strategy | Trades | Win% | Total P&L | Avg P&L/trade |
|----------|--------|------|-----------|---------------|
| ORDER_BLOCK_REVERSAL | 448.0 | 48.0% | $1,396.20 | $3.12 |
| DAY_LOW_BULLISH | 74.0 | 59.5% | $1,209.04 | $16.34 |
| ENHANCED_BULLISH | 74.0 | 59.5% | $1,209.04 | $16.34 |
| INSTITUTIONAL_SUPPORT | 336.0 | 45.2% | $1,036.09 | $3.08 |
| LONDON_BREAKOUT | 20.0 | 85.0% | $800.15 | $40.01 |
| DAY_HIGH_BEARISH | 171.0 | 52.6% | $678.68 | $3.97 |
| ENHANCED_BEARISH | 171.0 | 52.6% | $678.68 | $3.97 |
| VOLUME_CLIMAX | 80.0 | 56.2% | $622.94 | $7.79 |
| BULL_TREND_FOLLOWER | 782.0 | 50.9% | $598.77 | $0.77 |
| PIP_BLAST | 1921.0 | 39.9% | $-180.70 | $-0.09 |

---

## 💱 Symbol Breakdown

| Symbol | Trades | Win% | Total P&L |
|--------|--------|------|-----------|
| SILVER | 100.0 | 44.0% | $3,294.50 |
| GOLD | 174.0 | 63.8% | $2,890.68 |
| BTCUSD | 780.0 | 49.5% | $1,122.58 |
| AUDUSD | 549.0 | 38.1% | $249.42 |
| USDJPY | 475.0 | 29.9% | $202.28 |
| GBPUSD | 621.0 | 45.2% | $161.02 |
| EURUSD | 665.0 | 32.0% | $110.89 |
| ETHUSD | 713.0 | 66.6% | $17.52 |

---

## 🤖 ML Model Impact

- No ML model found. All trades used base lot of 0.02.
- Run `ml_experiment_pipeline.py` to train a model and improve sizing.

---

## 🚀 Next Steps

1. **Train the ML model** (`python ml_experiment_pipeline.py`) for smarter sizing
2. **Fetch 1-year data** (`python fetch_one_year_data.py`) to improve training
3. **Re-run this script** after training to compare ML vs RAW performance
4. **Adjust threshold** (currently 0.55) if you want more/less conservative sizing
