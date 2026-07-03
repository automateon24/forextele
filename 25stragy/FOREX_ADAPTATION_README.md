# Forex Adaptation Guide: AutomateON Core Engine

## Project Overview
This repository contains the full source code for the **AutomateON V15 AI Trading System** and **Telegram Signal Aggregator**. It was originally designed to autonomously manage options trading on the Indian Stock Market (Nifty, BankNifty, Sensex) through Dhan API. 

The architecture is highly modular and has now been prepared for seamless adaptation to the **Global Forex Market (MT5/XM-Global)**.

## Core Components
1. **`dashboard_server.py`**: The real-time Flask web dashboard. It acts as the central command center, rendering live PNL, active trades, and historical data across multiple strategies simultaneously.
2. **`engine_v15.py`**: The autonomous trading executor. It handles live market data polling, dynamic trailing stop losses (TSL), margin checking, and order execution.
3. **`gap_rule_engine.py`**: A generative ML-driven prediction system that uses daily market sentiment (VIX, institutional data) to predict market gaps and take pre-close positions.
4. **`telegram_signal_engine.py`**: A scraper and NLP parser that connects to premium Telegram signal channels, translates human-readable signals into JSON, and passes them to the engine for execution.

## Adapting for Forex (MT5)
To successfully deploy this infrastructure for Forex trading on MetaTrader 5, follow these steps:

### 1. Symbol Mapping
Indian indices (`NIFTY 07 JUL 24400 CE`) have expiration dates and strike prices. Forex symbols (`XAUUSD`, `EURUSD`, `GBPUSD`) are spot instruments.
* **Update `telegram_signal_engine.py`**: Modify the Regex parsers to identify Forex symbols instead of Option chains. Remove expiration and strike price extraction logic.
* **Update Dashboard UI**: Remove the "Greeks (Delta/Theta)" HTML blocks from `dashboard_server.py` as they do not apply to spot Forex. 

### 2. Live Market Data (CMP)
The current system fetches live prices via Dhan API. 
* **Replace Dhan API**: You must integrate the `MetaTrader5` Python library (`import MetaTrader5 as mt5`).
* **Update `market_data_fetcher.py`**: Route the `get_ltp()` requests to query `mt5.symbol_info_tick(symbol).ask`.

### 3. Lot Sizing and Margin
* Options use fixed lot sizes (e.g., Nifty = 25). Forex uses standard, mini, and micro lots (e.g., 1.0 = 100,000 units).
* **Update `engine_v15.py`**: Remove the fixed lot size mapping (`INDEX_CONFIGS`). Implement a dynamic risk-based lot sizing calculator based on Account Equity and Stop Loss pip distance.

### 4. Overriding the EOD Sweep
The Indian market closes at 15:30 IST, and the system sweeps non-overnight trades. Forex runs 24/5.
* **Remove EOD Close**: Inside `dashboard_server.py`, remove the `"EOD_CLOSE"` sweep logic for Active Trades. Let MT5's Take Profit (TP) and Stop Loss (SL) handle the closures entirely.

## Startup Instructions
1. Open this project in your preferred IDE (Cursor/VSCode).
2. Install MT5 library: `pip install MetaTrader5`
3. Connect your MT5 terminal to the XM-Global Server.
4. Run `START_TELEGRAM_ENGINE.bat` to begin scraping Forex signals.
5. Launch `dashboard_server.py` to monitor your trades.
