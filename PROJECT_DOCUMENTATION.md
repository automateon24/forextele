# FOREX AI SWARM OS - SYSTEM DOCUMENTATION

## Overview
The **Forex AI Swarm OS** is an autonomous trading engine that combines live algorithmic strategy execution with Generative AI-driven Telegram signal parsing. It acts as a bridge between unstructured Telegram messages across 50+ channels and a strict, risk-managed MT5 Execution Engine.

## Core Modules

### 1. Telegram Signal Parser (`telegram_signal_engine.py`)
- Continuously scrapes messages from authorized Telegram sessions (`Account1` and `Account2`).
- Relies on **Ollama / Llama 3.2** to extract structured trading data (Symbol, Action, Entry, SL, TP).
- **Recent Upgrade:** The AI prompt has been hardened to parse complex price ranges (e.g. `4030/4035`) and strictly rejects non-supported crypto pairs (like GALA, SYN) to prevent MT5 invalid pair errors. 

### 2. MT5 Execution Engine (`real_mt5_execution.py`)
- Acts as the risk gateway before hitting the live market.
- Converts parsed Telegram signals into `mt5.order_send` payloads.
- **Duplicate Prevention:** Before placing an order, it scans all open positions. If an active position for the exact Symbol and Magic Number already exists, it blocks the new trade. This prevents the "Stacked Orders" bug where channels repeatedly post the same signal causing massive drawdown.
- **Dynamic ATR Stops:** If a signal provides no SL or TP, the engine automatically calculates the live 14-period ATR and injects safe stop boundaries.

### 3. Ultimate Strategy Engine (`live_strategy_executor.py`)
- Runs 40+ dynamic AI/ML strategies in parallel (e.g., Breakout, RSI Reversal, Golden Hours).
- Computes lot sizing dynamically using an Anti-Martingale Kelly criterion risk model.
- **Trailing Stop Manager:** A background thread dynamically trails stops. Recently patched to verify broker `RETCODE_DONE` before logging, preventing infinite loop spam and broker rate-limiting.
- **Circuit Breaker:** The daily 3% loss circuit breaker was disabled as per administrative override to allow unconstrained ML data gathering.

### 4. React Dashboard (`dashboard_ui`)
- An interactive React + Vite frontend running on `localhost:5555`.
- Provides real-time websocket (`localhost:8888`) updates on open positions, separated into **Ultimate Strategies** and **Telegram Signals** ledgers.
- The Telegram tab features a deep-dive expandable view showing the raw message, the parsed output, and the exact Execution Status (Success, Rejected, etc).
- The channel name that originated the signal is now cleanly passed to the MT5 position comment and displayed on the dashboard for absolute transparency.

## Deployment & Startup
1. Close all running Python and Node processes.
2. Run `START_SWARM_OS.bat` located in `C:\anlyzeforex\forextele`.
3. The script sweeps ghost processes and launches the Master Python Backend and the React Frontend simultaneously.
4. View the dashboard at `http://localhost:5555`.

## Known Constraints
- The system is configured to run in "data-gathering" mode for the next 30 days to observe the raw, unfiltered performance of all 50+ channels.
