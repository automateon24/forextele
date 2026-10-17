# SepPro-Enhanced Hybrid Institutional 30-Day Master Report ($3,000 Capital)
**Date:** 2026-10-17 11:47:15 UTC  
**Evaluation Window:** Last 30 Calendar Days (Sept 17, 2026 - Oct 17, 2026)  
**Execution Precision:** Real MT5 M5 Execution with M15/H1 Multi-Timeframe Confluence  
**Data Integrity:** Zero Intra-Bar Peek Bias (Hard SL evaluated before TP on every bar), Real Live Spreads, $7/lot Commission, Slippage  
**AI Machine Learning Integration:** `final_model_sucess.joblib` (Trained Random Forest Classifier)  
**SepPro Institutional Enhancements:**
1. **SepPro Anti-Top/Bottom Guard:** Blocked extended entries ($>2.8\times\text{ATR}$ away from EMA50).
2. **Wyckoff Liquidity Sweep Detection:** +25% Conviction Boost on Springs & Upthrusts.
3. **Institutional 2-Target Asymmetric Scaling & Pyramiding:** 50% locked at 1.8R, 25% pyramided on trend continuation, 50-75% trailed to 3.0R+.
4. **Dynamic Symbol Gating & Quarantine:** Automatically bypasses instruments with $\ge 2$ consecutive losses in a week, redirecting lot budget to Gold & BTC.
5. **Institutional Risk Shield:** Strict max lot caps preventing overleveraging.
**Compounding Model:** Model 3 AI Conviction Dynamic Kelly with Dynamic Equity Scaling    

---

## 1. 30-Day Executive Performance
* **Starting Capital:** $3,000.00 USD
* **Final Balance (Today):** **$5,256.72 USD**
* **Net Profit in 30 Days:** **$+2,256.72 USD**
* **30-Day Return on Investment (ROI):** **+75.22%**
* **Total Closed Trades:** 74
* **Win / Loss Record:** 37 Wins / 37 Losses (**50.00% Win Rate**)
* **Profit Factor:** **1.81**
* **Maximum Historical Drawdown:** **$609.26 USD (10.87%)**

---

## 2. Asset Attribution (Last 30 Days)
| Symbol | Total Trades | Wins | Losses | Win Rate | Net PnL (USD) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **GOLD** | 33 | 19 | 14 | 57.6% | **$+1,924.73** |
| **SILVER** | 6 | 1 | 5 | 16.7% | **$-259.02** |
| **BTCUSD** | 13 | 8 | 5 | 61.5% | **$+595.11** |
| **ETHUSD** | 2 | 1 | 1 | 50.0% | **$+2.62** |
| **EURUSD** | 6 | 4 | 2 | 66.7% | **$+165.06** |
| **GBPUSD** | 3 | 0 | 3 | 0.0% | **$-150.10** |
| **USDJPY** | 11 | 4 | 7 | 36.4% | **$-21.70** |

---

## 3. Strategy Attribution (Last 30 Days)
| Strategy | Total Trades | Wins | Losses | Win Rate | Net PnL (USD) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **HYBRID_DILSE_PULL** | 69 | 33 | 36 | 47.8% | **$+1,962.65** |
| **BREAKOUT_BOSS_CORE** | 5 | 4 | 1 | 80.0% | **$+294.05** |

---

## 4. Week-by-Week Verified Progression
| Calendar Week | Trades | Wins | Win Rate | Net PnL (USD) |
| :--- | :---: | :---: | :---: | :---: |
| **Week 38** | 5 | 5 | 100.0% | **$+420.23** |
| **Week 39** | 16 | 9 | 56.2% | **$+664.13** |
| **Week 40** | 18 | 9 | 50.0% | **$+740.64** |
| **Week 41** | 22 | 8 | 36.4% | **$+487.58** |
| **Week 42** | 13 | 6 | 46.2% | **$-55.88** |

---

## 5. Production Deployment Status
* All mathematical rules, session windows, trained AI ML model (`final_model_sucess.joblib`), SepPro Anti-Top Guard, Wyckoff Conviction Boost, and Model 3 AI Kelly dynamic lot formulas are ready to be utilized directly by live trading daemons.
* Saved raw trades to: `C:\anlyzeforex\forextele\reports\hybrid_institutional_last_1month_trades.csv`
