# SepPro-Enhanced Hybrid Institutional 30-Day Master Report ($3,000 Capital)
**Date:** 2026-10-17 11:09:51 UTC  
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
* **Final Balance (Today):** **$3,286.97 USD**
* **Net Profit in 30 Days:** **$+286.97 USD**
* **30-Day Return on Investment (ROI):** **+9.57%**
* **Total Closed Trades:** 88
* **Win / Loss Record:** 36 Wins / 52 Losses (**40.91% Win Rate**)
* **Profit Factor:** **1.11**
* **Maximum Historical Drawdown:** **$570.80 USD (14.80%)**

---

## 2. Asset Attribution (Last 30 Days)
| Symbol | Total Trades | Wins | Losses | Win Rate | Net PnL (USD) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **GOLD** | 50 | 21 | 29 | 42.0% | **$+215.13** |
| **SILVER** | 15 | 4 | 11 | 26.7% | **$-169.74** |
| **BTCUSD** | 11 | 7 | 4 | 63.6% | **$+284.51** |
| **EURUSD** | 12 | 4 | 8 | 33.3% | **$-42.93** |

---

## 3. Strategy Attribution (Last 30 Days)
| Strategy | Total Trades | Wins | Losses | Win Rate | Net PnL (USD) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **HYBRID_DILSE_PULL** | 82 | 33 | 49 | 40.2% | **$+235.02** |
| **BREAKOUT_BOSS_CORE** | 6 | 3 | 3 | 50.0% | **$+51.95** |

---

## 4. Week-by-Week Verified Progression
| Calendar Week | Trades | Wins | Win Rate | Net PnL (USD) |
| :--- | :---: | :---: | :---: | :---: |
| **Week 38** | 6 | 4 | 66.7% | **$+156.52** |
| **Week 39** | 18 | 8 | 44.4% | **$+186.54** |
| **Week 40** | 19 | 8 | 42.1% | **$+63.40** |
| **Week 41** | 25 | 11 | 44.0% | **$+328.86** |
| **Week 42** | 20 | 5 | 25.0% | **$-448.35** |

---

## 5. Production Deployment Status
* All mathematical rules, session windows, trained AI ML model (`final_model_sucess.joblib`), SepPro Anti-Top Guard, Wyckoff Conviction Boost, and Model 3 AI Kelly dynamic lot formulas are ready to be utilized directly by live trading daemons.
* Saved raw trades to: `C:\anlyzeforex\forextele\reports\hybrid_institutional_last_1month_trades.csv`
