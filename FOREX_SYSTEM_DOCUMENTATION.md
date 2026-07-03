# AutomateON - Global Forex & Crypto Trading System
**Version:** 2.0 (Migration from Indian Options to XM-Global MT5)
**Date:** July 2026

## Overview
This document outlines the complete architecture, strategies, and operational parameters of the AI-driven trading system designed for Global Markets (Forex, Gold, and Crypto). The system has been fully migrated from its original Indian Market (Dhan/Shoonya) foundation to support 24/7 global operations via MetaTrader 5 (MT5).

## 1. Core Architecture
- **Broker Interface:** MetaTrader 5 via `MetaTrader5` Python library.
- **Account:** XM-Global Demo (ID: `167573094`, Server: `XMGlobal-MT5`).
- **Capital Allocation:** $3,000 Total Capital (Allocated at $200 per Pair/Asset).
- **Execution Engine:** `live_order_executor.py` handles real-time execution, lot sizing, and 30-minute auto-close logic.
- **UI Dashboard:** `dashboard_flask.py` provides a tab-based command center for Strategy Allocation and Telegram Channel tracking.

## 2. Trading Strategies (39 Total)
The 36 legacy Indian Option strategies have been fully ported to spot assets by removing Greeks (Delta, Theta) and Strike Dependencies. Three specialized Global strategies were added.

### Key Strategy Groups:
1. **Trend & Momentum (Ported from V3/V4):** Standard Trend Following mapped directly to `BUY/SELL`.
2. **Session Based (New for Forex):**
   - `LONDON_BREAKOUT`: Triggers at 08:00 UTC.
   - `NY_OPEN_REVERSAL`: Triggers at 13:30 UTC.
   - `ASIAN_RANGE_SCALP`: Triggers at 00:00 UTC.
3. **News Breakout (Straddle Engine):** 
   - Uses MT5 Pending Orders (`Buy Stop` / `Sell Stop`) placed 10 pips above/below CMP immediately prior to major economic news releases.

## 3. Dual-Account Telegram AI Pipeline
The system listens to Telegram channels across two separate accounts (Primary + `9008400969`) to bypass joining limits.

**AI Processing (Gemini/OpenAI):**
- Unstructured messages are parsed by generative AI into strict `ACTION SYMBOL ENTRY LOT` format.
- `live_order_executor.py` filters these against the active market sessions to enforce volatility safety constraints.

### The 25 Elite VIP Whitelist
Through algorithmic evaluation of over 250 channels, 25 high-purity (5-Star) sources have been hard-locked into the live engine:

**Gold / Forex Focus:**
1. Scalping Gold
2. GOLD Snipers
3. Sureshot FX
4. SureShot GOLD (VIP)
5. Sureshot FX VIP
6. GOLD TRADE SIGNALS
7. ZERO TO HERO PRIMIUM GROUP
8. EASY FOREX
9. GOLD TRADER
10. GLOBAL GOLD INSIGHT
11. GLOBAL PROFIT CLUB
12. tradebussunessfx_007
13. GOLD_MAST78
14. forexero
15. forexking1132

**Crypto / Mixed Focus:**
16. Market Trader Crypto Forex
17. Coin Chief
18. Binance Killers VIP
19. Crypto World Updates
20. Binance 360
21. DIL SE TRADER Crypto
22. CryptoSimplicity News
23. Crypto Radar
24. King Crypto Scalp [ LIVE ]
25. earlypumpdetector

## 4. Weekend vs Weekday Operation
- **Forex & Metals (Gold/Silver):** Trading is active 24/5 (Closes Friday night, opens Sunday night).
- **Crypto (BTC/ETH):** Trading continues 24/7.
The `live_order_executor.py` natively supports 24/7 continuous execution, gracefully handling `Market Closed` errors for Forex pairs while allowing Crypto orders to process during the weekend.

## 5. Security & Deployment
- The system prevents duplicate order firing using a state tracker and message hash.
- **GitHub Repository:** `automateon24/forextele` (Created to separate concerns from the `India_trade` core repo).
- Passwords and API keys are isolated in `ai_config.json` and `mt5_config.json`.
