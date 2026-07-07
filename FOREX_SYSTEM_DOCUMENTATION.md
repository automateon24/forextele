# AutomateON - Forex AI Swarm System Documentation

## System Overview
The AutomateON Forex AI Swarm is an autonomous, decentralized, multi-agent trading system designed to ingest Telegram signals, parse them using LLMs (Ollama), manage dynamic risk execution on MT5, and display real-time telemetry on an institutional React dashboard.

## Core Services (The Swarm)
The architecture is orchestrated by the **Master Swarm Runner** (`master_swarm_runner.py`), which launches and actively monitors the following isolated services via a 24/7 Health Monitor thread:

1. **Telegram Signal Engine (`telegram_signal_engine.py`)**
   - **Dual-Account Listener**: Connects to both `telegram_session.session` and `telegram_session2.session` concurrently via Telethon.
   - **VIP Channel Filter**: Hardcoded to strictly scan exactly 23 verified VIP channels across Crypto and Forex/Gold categories.
   - **Spam Filtering**: All messages are forwarded to Ollama, which intrinsically filters out junk and promotional messages.

2. **AI Strategy Executor (`live_strategy_executor.py`)**
   - Implements automated technical analysis (e.g., Breakout V15 strategy) over 8 core assets.
   - Applies strict market gap logic to prevent trading during weekend/rollover gaps.
   - Calculates dynamic lot sizing to enforce a rigid 1% risk per trade based on equity and SL distance.

3. **Position Manager & Trail Boss (`swarm_position_manager.py`)**
   - Monitors active MT5 positions independently of the entry logic.
   - Applies dynamic Trailing Stop Loss logic using ATR calculations to lock in profits automatically.

4. **WebSocket Telemetry Bridge (`dashboard_websocket.py`)**
   - Runs a WebSocket server on Port 8888.
   - Pushes live asset prices, spreads, open position status, and win-rate metrics using a strict 24-hour MT5 deal history to the frontend UI.

## Institutional Dashboard (UI/UX)
- Located in `C:\anlyzeforex\Ai_forextele\dashboard_ui`.
- **4x2 Compact CSS Grid**: Displays 8 assets across 2 rows. 
  - Row 1: EURUSD, GBPUSD, USDJPY, AUDUSD. 
  - Row 2: GOLD, SILVER, BTCUSD, ETHUSD.
- Features a completely dark-themed, metallic institutional design that parses MT5 JSON data feeds securely.

## Operational Procedures & QA
- **Crash Recovery**: If any component (e.g., the WebSocket or MT5 API) faults, the Master Runner intercepts the failure and re-spawns the thread automatically.
- **QA Code Cleansing**: All Unicode/emoji printing has been scrubbed from `master_swarm_runner.py` to prevent Windows console encoding crashes, guaranteeing uninterrupted 24/7 lifecycle.
- **System Launch**: The entire environment can be initialized by running `py master_swarm_runner.py` inside the root directory.
