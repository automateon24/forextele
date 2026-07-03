# STRAGY V15 + TELEGRAM AI PIPELINE
## Comprehensive Architecture & Setup Guide

### 1. The Autonomous AI Tracking Pipeline
We have fundamentally upgraded the Telegram integration. Rather than passively listening to signals, the `engine_v15.py` now autonomously manages open Telegram trades.

**How it works:**
1. The Telegram scraper (`telegram_signal_engine.py`) writes `NEW_SIGNAL` rows to `telegram_signals.xlsx`.
2. The core Trading Engine (`engine_v15.py`) intercepts these trades live on every 10-second heartbeat.
3. The AI resolves the instrument name into a valid Dhan security ID automatically using the Option Chain cache.
4. The AI independently polls the live LTP for the instrument and enforces a Trailing Stop Loss (TSL).
5. Once profit hits +15% from entry, the AI locks in a 5% TSL floor.
6. If the price falls back down and breaches the floor, the AI overrides the trade, logs the exact `exit_time` and `pnl`, and marks it as `TSL_HIT_AT_COST` or `T3_HIT`. 

### 2. Maximum Robustness & Auto-Recovery
The system is now completely immortal against crashes, timeouts, and dirty data.

*   **Process Crash Auto-Reboot:** `RUN_STRAGY_V15.bat` features an infinite `goto` loop. If the Python script crashes for any reason (memory leak, fatal network disconnect, manual kill), the batch file catches the non-zero exit code, waits 15 seconds, and forcibly restarts the `engine_v15.py` process.
*   **State Recovery Persistence:** The AI actively writes the `highest_premium` for every Telegram trade directly into `telegram_signals.xlsx`. If the system reboots mid-trade, the AI instantly recovers the historical peak price from Excel, guaranteeing the Trailing Stop Loss mathematically resumes exactly where it left off.
*   **API Rate Limit Shields:** `engine_v15.py` utilizes a strict `threading.Lock()` enforcing a 500ms global throttle. If Dhan issues an `805 Too Many Requests` error, the engine seamlessly executes an exponential backoff loop without interrupting the main processes.
*   **Dirty Data Sanitization:** `NaN` values and `dtype` mismatches (which previously crashed Pandas) are now forcefully cast to `.astype('object')` and sanitized to `0.0`.

### 3. The Unified Dashboard
The `dashboard_server.py` Javascript has been rewritten:
*   Resolved the hardcoded `"0 Closed"` bug, enabling dynamic rendering of `active_trades` and `completed_trades` length.
*   Removed `undefined` UI freezing for trades that lacked standard timestamps.
*   The dashboard cleanly displays internal AI overrides like `CLOSED_SL` and `TSL_HIT_AT_COST`.

---

## Standalone Deployment Guide (`trade_combined_worked`)
This folder (`trade_combined_worked`) contains the perfectly synchronized engine. It combines the components from `25stragy` and `niftyopt` into one transportable system.

### Installation Instructions
1. **Move the Directory:** Copy the entire `trade_combined_worked` folder onto your target system (e.g. VPS or local desktop).
2. **Environment Setup:** Ensure Python 3.11 is installed. Open a terminal inside the folder and create a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Configuration:** 
   - Open `config\dhan_tokens.json` and ensure your `CLIENT_ID` and `access_token` are updated for the new system.
   - Run the `DAILY_AUTO_LOGIN.bat` to verify connectivity.
4. **Launch Engines:**
   - Run `START_TELEGRAM_ENGINE.bat` to begin scraping signals.
   - Run `RUN_STRAGY_V15.bat` to start the live autonomous AI manager.
   - Run `START_UNIFIED_DASHBOARD.bat` to monitor the operation.

The system will now run infinitely, executing and closing signals autonomously.
