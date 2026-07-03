# Expiry Day Option Spikes Analysis (2x to 40x+ Jumps)

This report details the mathematical and structural conditions under which index option contracts (trading below ₹400) spike exponentially—doubling, tripling, or jumping **10x, 20x, to 40x+**—on their expiry days.

---

## **1. Top Spikes Recorded in the Dataset**

Our robust scan of 5,059 expired contract parquets identified **79 major spikes** on expiry days where a cheap contract rose by at least 2x. Below are the top 5 largest monster spikes:

| Index | Date | Type | Strike | Low Price | Peak Price | Start Time | Peak Time | **Multiplier** | OI Change | Spot Move |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **SENSEX** | 2026-04-30 | PE | ATM | **₹4.30** | **₹186.20** | 15:09 | 15:27 | **43.30x** | **-93.1%** | +0.291% |
| **NIFTY** | 2026-03-30 | PE | ATM | **₹2.15** | **₹74.80** | 15:15 | 15:25 | **34.79x** | **-58.8%** | +0.259% |
| **SENSEX** | 2026-04-30 | PE | ATM-1 | **₹2.60** | **₹86.70** | 15:19 | 15:27 | **33.35x** | **-54.5%** | +0.116% |
| **NIFTY** | 2026-03-30 | PE | ATM | **₹2.05** | **₹68.25** | 15:11 | 15:24 | **33.29x** | **-80.3%** | +0.239% |
| **SENSEX** | 2026-02-26 | PE | ATM | **₹2.10** | **₹59.25** | 15:14 | 15:15 | **28.21x** | **-67.3%** | +0.076% |

---

## **2. Why and When Do These Jumps Occur? (Core Mechanics)**

### **A. Time of Day: The 3:00 PM Afternoon Window**
Our timing analysis shows that these massive spikes are almost exclusively **late afternoon phenomena**:
* **Entry (Low Price) Window**: **75.9%** of the spikes establish their lowest value in the afternoon between **1:30 PM and 3:30 PM** (specifically concentrated between **3:00 PM and 3:15 PM**).
* **Peak (Exit Price) Window**: **79.7%** of the spikes hit their maximum peak between **3:00 PM and 3:28 PM**.
* **Rationale**: Prior to 3:00 PM, theta (time decay) is constantly crushing the option value, keeping premiums cheap (₹2 to ₹10). Once 3:00 PM hits, there is very little time left. If the underlying spot price suddenly moves, the delta of near-the-money options reacts explosively, and gamma dominates.

### **B. Short Covering (The Writer Exit Signature)**
The data confirms a massive, near-universal drop in **Open Interest (OI)** during the spike window:
* For **10x-20x jumps**, the average OI change was **-37.7%**.
* For **25x+ monster jumps**, the average OI change was **-70.8%** (and up to **-93.1%** in the 43x SENSEX jump!).
* **Rationale**: Option writers (sellers) who sold these contracts at high prices are caught off-guard. To prevent infinite losses as the option starts rising, they are forced to buy back their short positions at market price. This panic buying creates a short squeeze, propelling the option price straight up.

### **C. Spot Acceleration vs. Option Leverage**
The spot index does not need to move by 10% for the option to jump 30x. On expiry days, because the premium is so cheap, even a small spot move leads to massive percentage returns:
* **2x - 3x Jumps**: Spot moved by an average of **-0.01%** (mostly volatility/noise).
* **10x - 20x Jumps**: Spot moved by an average of **+0.09%**.
* **25x+ Monster Jumps**: Spot moved by an average of **+0.19%** (less than 0.2% change in the underlying index!).
* **Rationale**: Because SENSEX is trading around 75,000, a 0.2% move is **150 points**. At 3:15 PM on expiry day, if the spot moves 150 points, an out-of-the-money option (say, priced at ₹3) suddenly becomes deep in-the-money with an intrinsic value of ₹150. That is a **50x increase**!

---

## **3. Summary of Key Expiry Spike Conditions**

1. **Option Price Range**: The ideal starting price is **₹2.00 to ₹15.00** (higher starting prices like ₹100 rarely see 20x jumps because they require a massive, impossible index move).
2. **Timing**: Look for setups forming between **3:00 PM and 3:15 PM**.
3. **Trigger**: A sudden breakout in the spot index (e.g. 30-50 points on NIFTY or 100-150 points on SENSEX) accompanied by a rapid decrease in Open Interest (OI) as writers begin covering their shorts.
