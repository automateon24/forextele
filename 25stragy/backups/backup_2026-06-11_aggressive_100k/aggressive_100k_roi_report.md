# Aggressive Setup Performance Report: ₹100,000 per Index

This report details the backtest performance of the **Ultimate Unified Trading Engine** configured with an **Aggressive Capital Allocation** of **₹100,000 per index** (Total portfolio base: ₹4.0 Lakh).

To replicate the high-conviction style of manual trading, individual strategies are scaled to deploy a large portion of the index's capital base upon entry, while maintaining strict downside protections.

---

## **1. Performance Summary**

* **Total Portfolio Capital**: **Rs. 400,000** (₹1.0 Lakh per index)
* **Total Net Profit**: **Rs. +646,798.28**
* **Net ROI (155 Days)**: **161.7%**
* **Max Combined Drawdown**: **Rs. -32,637.15** (only **8.1%** of capital!)
* **Average Daily Profit**: **Rs. +5,053**
* **Daily ROI (on total capital)**: **1.26% / day**
* **Win Rate (Trades)**: **65.3%** (652 trades)
* **Green Days (Win Rate)**: **64.1%** (82 Green Days vs. 46 Red Days)

---

## **2. Daily Return & Trade Distribution**

* **Days making > 5% (Rs. 20,000+)**: **14 Days** (11.0% of all active trading days)
* **Days making > 10% (Rs. 40,000+)**: **5 Days** (4.0% of all active trading days)
* **Max Profit in a Single Day**: **Rs. +57,530.24** (**14.4% gain** in a single day)
* **Max Loss in a Single Day**: **Rs. -31,726.10** (**-7.9% loss** in a single day, strictly limited by circuit breakers)

---

## **3. Per-Index Performance Breakdown**

| Index | Trades | Win Rate (%) | Net PnL (Rs.) | Max Drawdown (Rs.) |
| :--- | :---: | :---: | :---: | :---: |
| **NIFTY** | 190 | 62.6% | **+Rs. 147,679.45** | Rs. -30,689.40 |
| **BANKNIFTY** | 153 | 65.4% | **+Rs. 110,401.58** | Rs. -29,682.66 |
| **FINNIFTY** | 156 | 67.3% | **+Rs. 184,295.73** | Rs. -37,463.00 |
| **SENSEX** | 153 | 66.7% | **+Rs. 204,421.52** | Rs. -26,520.80 |
| **COMBINED** | **652** | **65.3%** | **+Rs. 646,798.28** | **Rs. -32,637.15** |

---

## **4. Monthly Performance Matrix**

| Month | BANKNIFTY | FINNIFTY | NIFTY | SENSEX | **Combined Total** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Feb 2025** | +26,265.70 | +17,095.19 | +36,818.34 | +2,063.10 | **+Rs. 82,242.33** |
| **Mar 2025** | +27,248.34 | +11,719.30 | +21,313.39 | +973.69 | **+Rs. 61,254.72** |
| **Apr 2025** | +39,963.74 | +17,621.71 | +33,300.01 | +13,068.52 | **+Rs. 103,953.98** |
| **May 2025** | -3,970.00 | -3,776.00 | -3,985.00 | 0.00 | **-Rs. 11,731.00** |
| **Jan 2026** | +30,512.61 | +41,630.72 | +63,397.66 | +80,518.06 | **+Rs. 216,059.05** |
| **Feb 2026** | -14,027.35 | +63,410.07 | +16,949.74 | +43,214.65 | **+Rs. 109,547.11** |
| **Mar 2026** | +5,790.98 | +6,612.22 | -2,173.10 | 0.00 | **+Rs. 10,230.10** |
| **Apr 2026** | -103.50 | +66,531.04 | -11,097.93 | +28,852.09 | **+Rs. 84,181.70** |
| **May 2026** | -1,278.94 | -36,548.52 | -6,843.66 | +35,731.41 | **-Rs. 8,939.71** |
| **TOTAL** | **+110,401.58** | **+184,295.73** | **+147,679.45** | **+204,421.52** | **+Rs. 646,798.28** |

---

## **5. How the Setup Achieves Manual-like Profitability**

1. **High Strategy Sizing (60% to 90%)**:
   Unlike the conservative setup (which deploys 30% to 50% per trade), the Aggressive setup deploys **60% to 90%** of the index capital (₹60k to ₹90k out of the ₹100k index base) into a single trade. This mimics the manual trading style of putting significant conviction behind an entry.
2. **Intraday Capital Lock & Gating**:
   Because the first trade takes up 60% to 90% of the index's capital, any subsequent triggers on the same index are blocked by the concurrent margin checker. This enforces a "one or two trades at a time" discipline, preventing over-leveraging and noise trading.
3. **Daily Circuit Breakers**:
   The daily index circuit breaker is set to **-₹15,000** (15% of index capital). This acts as a hard stop. If an index hits a bad patch, the bot ceases trading on that index for the rest of the day, preserving the remaining ₹85,000.
