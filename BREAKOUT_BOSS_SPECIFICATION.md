# 👑 BREAKOUTBOSS v2: COMPLETE SYSTEM SPECIFICATION
**Asset:** Gold (`XAUUSD`) | **Platform:** MetaTrader 5 (XM Global Direct)  
**Script Path:** [`c:\anlyzeforex\forextele\breakout_boss_engine.py`](file:///c:/anlyzeforex/forextele/breakout_boss_engine.py)

---

## 1. STRATEGY FOUNDATIONS & MATHEMATICAL LOGIC

### A. Opening Range Construction
For each global session and timeframe $\Delta T \in \{1\text{m}, 5\text{m}\}$ starting at $T_0$:
- **Reference High ($H_{\text{ref}}$):** Highest quote of the opening candle.
- **Reference Low ($L_{\text{ref}}$):** Lowest quote of the opening candle.
- **Reference Range ($R_{\text{ref}}$):** $H_{\text{ref}} - L_{\text{ref}}$.
- **Midpoint ($M_{\text{ref}}$):** $(H_{\text{ref}} + L_{\text{ref}}) / 2.0$.

### B. Volatility Compression Gate
Prevents trading exhaustive news spikes or low-volatility dead traps:
$$\$0.35 \le R_{\text{ref}} \le \text{VolatilityCap}$$
- **M1 Cap:** $\$3.50$ (35 pips)
- **M5 Cap:** $\$6.50$ (65 pips)

### C. Retest & Rejection Confirmation
Does NOT buy on the breakout candle. Requires a retest pullback with confirmation:

#### Bullish Trigger (BUY):
1. Breakout: Price exceeds $H_{\text{ref}} + \$0.25$.
2. Retest Touch: Subsequent candle satisfies:
   $$\text{Low} \le H_{\text{ref}} + \$0.25 \quad \text{AND} \quad \text{High} \ge H_{\text{ref}} - \$0.25$$
3. Rejection: Retest candle must close green ($\text{Close} \ge \text{Open}$) or close above $H_{\text{ref}}$.
4. Invalidation: If price breaches below $L_{\text{ref}}$, setup is discarded.

#### Bearish Trigger (SELL):
1. Breakout: Price drops below $L_{\text{ref}} - \$0.25$.
2. Retest Touch: Subsequent candle satisfies:
   $$\text{High} \ge L_{\text{ref}} - \$0.25 \quad \text{AND} \quad \text{Low} \le L_{\text{ref}} + \$0.25$$
3. Rejection: Retest candle must close red ($\text{Close} \le \text{Open}$) or close below $L_{\text{ref}}$.
4. Invalidation: If price breaches above $H_{\text{ref}}$, setup is discarded.

---

## 2. GLOBAL SESSIONS & TIMEFRAME SCHEDULE

| Session Code | Session Name | Start Time (UTC) | IST (Indian Time) | MT5 Time | Timeframes | Target R:R | Backtest Edge |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **ASIA** | Asian Open | `01:00 UTC` | 06:30 AM | 04:00 | **M1** | **1:1.5** | M1 64.7% WR; M3/M5/M15 pruned. |
| **FRA** | Frankfurt Open | `06:00 UTC` | 11:30 AM | 09:00 | **M1, M5** | **1:5.0 (M1)<br>1:3.0 (M5)** | **#1 Session Worldwide: 76.9% WR, 9.21 PF.** |
| **LON** | London Core | `08:00 UTC` | 01:30 PM | 11:00 | **M1, M5** | **1:3.0** | **86.7% WR.** High institutional volume. |
| **NYP** | NY Pre-Market | `12:30 UTC` | 06:00 PM | 15:30 | **M1, M5** | **1:3.0** | Macro news expansion. |
| **NYC** | NY Cash Open | `13:30 UTC` | 07:00 PM | 16:30 | **M1, M5** | **1:5.0 (M1)<br>1:3.0 (M5)** | **92.3% WR.** Wall Street order flow. |
| **LNC** | London Close | `15:30 UTC` | 09:00 PM | 18:30 | **M1** | **1:3.0** | European daily fixing. |

> **Safeguard:** Max 1 trade setup per session per day to eliminate risk multiplication.

---

## 3. W.D. GANN HARMONIC TIMING CYCLES (CANDLE #72)

- **Timing:** Exactly the **72nd 1-minute candle** of the trading day (~`02:11 UTC` / `07:41 AM IST` / `05:11 MT5`).
- **Gann Theory:** 1,440 minutes in a full day. Candle #72 represents the 50% harmonic point of the first Asian quadrant ($144 / 2 = 72$).
- **Tokyo Liquidity Acceleration:** Coincides with the morning Asian bank fix.
- **Reference Range:** High and low of Candle #72 ($0.25 \le \text{Range} \le 8.00$).
- **Execution:** Breakout & retest executed at **1:1.5 R:R** with minimum risk floor of $\$0.60$ and **1.10x conviction multiplier**.

---

## 4. THE 5 COMPOUNDING MODELS (VIRTUAL BASKETS)

Total Allocation: **$5,000 USD** (5 virtual baskets $\times$ $1,000 each):

| Model | ID | Magic | Lot Sizing Formula | Role |
| :--- | :--- | :--- | :--- | :--- |
| **Baseline Fixed** | M0 | `555000` | `Lots = 0.02` (Constant) | Benchmark to measure strategy edge. |
| **Milestone Step-Ladder** | M1 | `555001` | $<\$1,400: 0.02$<br>$\$1,400-\$2,000: 0.03$<br>$\$2,000-\$2,800: 0.04$<br>$\$2,800-\$3,800: 0.06$<br>$\$3,800-\$5,000: 0.08$<br>$\ge \$5,000: 0.10$ | Tiered step up; locks in profits before increasing size. |
| **Linear Equity Dynamic** | M2 | `555002` | $\text{Lots} = (\text{Equity} / 1000) \times 0.02$ | Smooth proportional scaling. |
| **AI Conviction Weighted** | M3 | `555003` | $\text{Lots} = (\text{Equity} / 1000) \times 0.02 \times W_{\text{session}}$<br>FRA: 1.35x, LNC: 1.35x, NYC: 1.15x, LON: 1.00x, ASIA: 0.70x | Session win-rate weighting. |
| **Aggressive Half-Kelly** | M4 | `555004` | $\text{Lots} = (\text{Equity} / 1000) \times 0.03$ | Half-Kelly geometric growth. |

---

## 5. DYNAMIC QUOTE ANCHORING & ZERO-ERROR EXECUTION

To eliminate MetaTrader 5 error codes (`10016: Invalid Stops`, `10030: Unsupported Filling`):
1. **Live Tick Anchoring:** SL and TP are calculated relative to the *live fill quote* (`tick.ask` for BUY, `tick.bid` for SELL) fetched at the exact millisecond before `order_send()`.
2. **Min Risk Floor:** $\text{Risk} = \max(\text{Entry} - \text{SL}, \$1.20)$ (prevents spread eating tight SL).
3. **IOC Filling:** Uses `ORDER_FILLING_IOC` with a 25-point slippage tolerance and automatic 150ms retry.

---

## 6. TWO-STAGE TRAILING STOP LOSS (TSL) & EOD CLOSE

- **Stage 1 (Breakeven Lock at +1.5R):**
  When floating profit reaches $+1.5\text{R}$, SL is modified to $\text{Entry} \pm \$0.20$ (locks in trade completely risk-free).
- **Stage 2 (Momentum Trailing Stop at +2.5R):**
  Once profit exceeds $+2.5\text{R}$, SL trails market price at a $1.5\text{R}$ distance in discrete steps of at least $\$0.30$.
- **Mandatory EOD Force-Close:**
  All open positions automatically closed at **`20:50 UTC`** (03:20 AM IST / 23:50 MT5) before the 1-hour rollover pause (21:00–22:00 UTC) to avoid wide rollover spreads.
