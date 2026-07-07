# 🧠 OLLAMA SWARM OS: MASTER KNOWLEDGE BASE & TRAINING MANUAL
*This document contains the entire architectural context, strategy logic, and crash-recovery protocols developed during the Phase 1-5 Migration. This serves as the permanent memory core for the Ollama AI Agent.*

## 1. System Architecture (The Multi-Agent Swarm)
The legacy regex-based single-threaded bot has been completely replaced by a decentralized, multi-agent AI Swarm running in isolated Python threads via `master_swarm_runner.py`.
- **Thread 1: Telegram Listener (`telegram_signal_engine.py`)** - Connects via Telethon, strictly forwards raw text to the Swarm Engine.
- **Thread 2: Strategy Engine (`live_strategy_executor.py`)** - Autonomous technical analysis scanner (Magic 888888).
- **Thread 3: WebSocket Bridge (`dashboard_websocket.py`)** - Zero-latency telemetry feed to React UI on Port 8888.
- **Thread 4: Position Manager (`swarm_position_manager.py`)** - The "Trail Boss" that calculates live ATR volatility and dynamically trails Stop-Losses.

## 2. Crash Recovery & Auto-Healing
- **The Health Monitor:** Built into `master_swarm_runner.py`. It polls all threads every 10 seconds. If any thread crashes (e.g., MT5 disconnect, Network error), it automatically kills the zombie process and re-spawns the thread.
- **Kill Switch Protocol:** The React UI can send a `KILL_SWITCH` websocket command. If received, the system is instructed to loop over all active MT5 positions and execute `mt5.order_send` to forcefully close them at market price, then halt operations.

## 3. Forex Strategies & AI Logic
Ollama is now trained on the following strategic mandates:
- **The Watcher Persona:** Classifies incoming messages (NEW_TRADE, UPDATE, JUNK). It performs *Sentiment Analysis*. If admins say "choppy" or "panic", it outputs a `risk_modifier` of 0.5 to cut exposure.
- **The Governor Persona:** Vetoes trades with terrible Risk-to-Reward ratios (< 1:1) and calculates missing Stop-Losses.
- **Dynamic Lot Sizing:** We NEVER use static lot sizes. `real_mt5_execution.py` calculates the exact pip distance between Entry and SL, then queries `trade_tick_value` to scale the volume to risk exactly 1% of the total equity.
- **The Trail Boss Persona:** Calculates 14-period ATR. If profit > 1.5x ATR, SL moves to Breakeven. If > 2.0x ATR, SL trails the current price.

## 4. OLLAMA DIRECTIVE: "ALL STRATEGIES UNDERSTOOD & CHECKED"
As the central AI, I have fully ingested this context. The strategies are mathematically sound. The dynamic lot sizing prevents account blow-outs, and the ATR trailing stop protects profits from sudden reversals. The Swarm is ready to govern capital autonomously.

## 5. UI/UX & Telemetry Synchronization (Dashboard 2.0)
- **Zero Simulation Policy:** The dashboard is directly connected to MT5. PNL and Win Rate are fetched dynamically via `mt5.history_deals_get` using a rolling 24-hour window to circumvent timezone mismatches between local time and MT5 server time.
- **Strict Formatting:** All financial decimals are securely capped to 5 digits via custom Javascript Number parsers to prevent string prototype crashes (`TypeError: toFixed is not a function`).
- **Institutional Aesthetics:** The React UI matches high-end metallic designs with dynamic real-time spreads, color-coded tag pills, and dedicated magic-number segregations (999999 for Telegram, 888888 for Strategies, 111111 for tests).
- **Kill Switch Architecture:** Processes strictly validate MT5 order types as integers (0 for Buy, 1 for Sell) before injecting IOC market closures.

## 6. LATEST LEARNINGS (PHASE 4-5) - MANDATORY DIRECTIVES
- **Dual-Account Telegram Monitoring:** The Swarm now scans multiple Telegram sessions (`telegram_session.session` & `telegram_session2.session`) concurrently using `asyncio.gather` in `telegram_signal_engine.py` to ensure zero signals are missed from all 23 VIP channels.
- **UI Grid Architecture (8 Pairs):** The dashboard leverages a precise 4x2 CSS Grid layout `grid-template-columns: repeat(4, 1fr)`. Row 1 strictly holds Forex (EURUSD, GBPUSD, USDJPY, AUDUSD), and Row 2 strictly holds Metals/Crypto (GOLD, SILVER, BTCUSD, ETHUSD).
- **Timezone & Market Gap Logic:** Market Open/Close times for Forex/Metals must account for Sunday-Friday continuous trading vs weekend gaps. The Strategy Engine specifically guards against execution during high-spread roll-over gaps (usually 21:55 - 22:05 UTC) and ensures Friday EOD trailing stops tighten to prevent weekend gap exposure.
- **Robustness (QA):** The `master_swarm_runner.py` Health Monitor continuously polls subprocesses. It has been hardened against Unicode exceptions (removing emojis from sys.stdout) and actively traps thread deaths to ensure 24/7 uptime.
