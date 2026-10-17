# SepPro-Enhanced Hybrid Institutional 30-Day Master Report ($3,000 Capital)
**Date:** 2026-10-17 11:34:47 UTC  
**Evaluation Window:** Last 30 Calendar Days (Sept 17, 2026 - Oct 17, 2026)  
**Execution Precision:** Real MT5 M5 Execution with M15/H1 Multi-Timeframe Confluence  
**Data Integrity:** Zero Intra-Bar Peek Bias (Hard SL evaluated before TP on every bar), Real Live Spreads, $7/lot Commission, Slippage  
**AI Machine Learning Integration:** `final_model_sucess.joblib` (Trained Random Forest Classifier)  
**SepPro Institutional Enhancements:**
1. **SepPro Anti-Top/Bottom Guard:** Blocked extended entries ($>2.2\times\text{ATR}$ away from EMA50).
2. **Wyckoff Liquidity Sweep Detection:** +25% Conviction Boost on Springs & Upthrusts.
3. **Institutional 2-Target Asymmetric Scaling:** 50% locked at 1.8R, 50% trailed to 3.0R+.
4. **Institutional Risk Shield:** Strict max lot caps (0.07 Gold, 0.08 BTCUSD, 0.03 Silver) preventing overleveraging.
**Compounding Model:** Model 3 AI Conviction Dynamic Kelly  

---

## 1. 30-Day Executive Performance
* **Starting Capital:** $3,000.00 USD
* **Final Balance (Today):** **$4,843.09 USD**
* **Net Profit in 30 Days:** **$+1,843.09 USD**
* **30-Day Return on Investment (ROI):** **+61.44%**
* **Total Closed Trades:** 77
* **Win / Loss Record:** 40 Wins / 37 Losses (**51.95% Win Rate**)
* **Profit Factor:** **1.75**
* **Maximum Historical Drawdown:** **$534.24 USD (10.41%)**

---

## 2. Asset Attribution (Last 30 Days)
| Symbol | Total Trades | Wins | Losses | Win Rate | Net PnL (USD) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **GOLD** | 33 | 19 | 14 | 57.6% | **$+1,384.51** |
| **SILVER** | 8 | 3 | 5 | 37.5% | **$+52.26** |
| **BTCUSD** | 13 | 8 | 5 | 61.5% | **$+399.31** |
| **ETHUSD** | 2 | 1 | 1 | 50.0% | **$+1.99** |
| **EURUSD** | 6 | 4 | 2 | 66.7% | **$+131.46** |
| **GBPUSD** | 3 | 0 | 3 | 0.0% | **$-142.20** |
| **USDJPY** | 12 | 5 | 7 | 41.7% | **$+15.74** |

---

## 3. Strategy Attribution (Last 30 Days)
| Strategy | Total Trades | Wins | Losses | Win Rate | Net PnL (USD) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **HYBRID_DILSE_PULL** | 72 | 36 | 36 | 50.0% | **$+1,575.56** |
| **BREAKOUT_BOSS_CORE** | 5 | 4 | 1 | 80.0% | **$+267.51** |

---

## 4. Week-by-Week Verified Progression
| Calendar Week | Trades | Wins | Win Rate | Net PnL (USD) |
| :--- | :---: | :---: | :---: | :---: |
| **Week 38** | 5 | 5 | 100.0% | **$+345.05** |
| **Week 39** | 16 | 9 | 56.2% | **$+533.23** |
| **Week 40** | 18 | 9 | 50.0% | **$+492.25** |
| **Week 41** | 25 | 11 | 44.0% | **$+519.58** |
| **Week 42** | 13 | 6 | 46.2% | **$-47.04** |

---

## 5. Production Deployment Status
* All mathematical rules, session windows, trained AI ML model (`final_model_sucess.joblib`), SepPro Anti-Top Guard, Wyckoff Conviction Boost, and Model 3 AI Kelly dynamic lot formulas are ready to be utilized directly by live trading daemons.
* Saved raw trades to: `C:\anlyzeforex\forextele\reports\hybrid_institutional_last_1month_trades.csv`
