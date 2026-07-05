# AutomateON AI Forex Trading Ecosystem (v4.0)
## Official System Architecture & Technical Documentation

**Workspace Path:** `C:\anlyzeforex\forextele\`
**Trading Platform:** MetaTrader 5 (XM-Global)
**Core Technologies:** Python 3, Concurrent Futures (Threading), Flask, Telethon (Telegram API), Pandas.

---

### 1. Executive Summary
The AutomateON v4.0 ecosystem is a fully autonomous, multi-threaded AI trading engine designed to execute high-frequency trades across 8 assets (Forex Majors, Crypto, Gold, Silver). It features dynamic 1000x compounding lot sizing, machine-learning optimized entry parameters ("DNA"), and a dual-pipeline architecture capable of executing both AI-algorithmic trades and parsed Telegram VIP signals simultaneously.

### 2. Core Architecture & Modules

#### A. AI Strategy Optimization Engine (`ml_dna_optimizer.py`)
*   **Purpose:** To prevent the AI from trading on stale logic by continually optimizing parameters against recent market conditions.
*   **Logic:** Uses historical M15 data to backtest 40 independent algorithmic strategies (e.g., `MOMENTUM_BURST`, `ORDER_BLOCK_REVERSAL`, `NEWS_BREAKOUT_STRADDLE`).
*   **Output:** Generates `ai_optimized_forex_dna.json`. This file acts as the absolute truth for the live execution engines, dictating the `tsl_a` (Trailing Stop Activation), `tsl_t` (Trailing Stop Factor), `sl`, and `tgt` thresholds uniquely calculated for each pair.

#### B. Live Strategy Execution Engine (`live_strategy_executor.py`)
*   **Purpose:** The algorithmic heartbeat of the system.
*   **Threading Model:** Utilizes `concurrent.futures.ThreadPoolExecutor`. Every asset class (e.g., GOLD, EURUSD) is assigned its own dedicated, infinite `while True` polling thread. This ensures zero latency and prevents high-volatility events on one pair from blocking the execution of another.
*   **Dynamic Margin Compounding:** Uses `calculate_dynamic_lot()`. It artificially partitions exactly $200 of margin per trade, multiplying it by 1000x leverage, and calculating the maximum mathematically allowable volume size to achieve 40%+ daily ROI targets safely.
*   **Trailing Stop Engine:** A dedicated background thread that scans all open positions tagged with `magic=888888`. It reads the unique DNA for that symbol and tightens the stop-loss tick-by-tick as the trade moves into profit.

#### C. Telegram Signal Execution Pipeline (`live_order_executor.py`)
*   **Purpose:** To parse, translate, and execute unstructured text signals from VIP Telegram Channels.
*   **Listener Engine:** Uses `Telethon` to bind to the Telegram API and actively listen to 25+ specific VIP channels.
*   **AI Parsing:** Uses a Generative AI prompt to translate chaotic message structures into strict `ACTION SYMBOL ENTRY_PRICE` logic.
*   **Autonomous ATR Fallback:** If a Telegram signal provides an entry but fails to provide a Stop Loss (SL) or Take Profit (TP), the system automatically queries the MT5 terminal for the 15-Minute Average True Range (ATR) and assigns a mathematically safe volatility-based SL/TP to protect the capital.
*   **Trade Logging:** Logs every execution into the central `master_trade_ledger.csv`, injecting the exact Telegram Channel name into the MT5 `comment` field (e.g., `Telegram : VIP Gold`) for precise tracking.

#### D. Mission Control Dashboard (`dashboard_flask.py`)
*   **Purpose:** A real-time, Glassmorphism-styled web interface (`127.0.0.1:5000`) for monitoring the autonomous engines.
*   **Telemetry:** Features a Javascript polling interval (1.5s) that dynamically renders the status of all AI Execution threads (e.g., *Active*, *Paused*, *Monitoring*) without requiring a page refresh.
*   **Master Control API:** Exposes the `/api/control/<action>` endpoint. Features professional toggle switches linked to the `control_flags.json` state machine:
    1.  `🚨 PANIC`: Immediately sends MT5 MARKET_CLOSE orders for all open positions.
    2.  `⏻ Toggle Core Engine`: Safely shuts down or spins up the multi-threading loop.
    3.  `⏸ Toggle AI`: Suspends AI algorithmic entries while leaving Telegram active.
    4.  `⏸ Toggle Telegram`: Suspends Telegram signal parsing.

### 3. State Management & Data Flow
*   `control_flags.json`: The global state file. Threads natively check this file on every loop iteration to determine if they should execute, sleep, or exit safely. Default state on boot is `RUNNING` for all systems.
*   `thread_status.json`: A dictionary file updated every 2 seconds by `live_strategy_executor.py`. The Flask dashboard reads this file to color-code the UI thread metrics.

### 4. Deployment & Operation
*   **Startup:** Execute `START_FOREX_SYSTEM.bat` (configured to use `py` and `cmd /k` for error persistence). This natively spins up the Telegram Listener, the Strategy Executor, and the Flask Dashboard in separate environments.
*   **Maintenance:** Weekly execution of `ml_dna_optimizer.py` is recommended to prevent market drift and keep the DNA thresholds hyper-accurate to the current macroeconomic environment.
