# 🚀 THE FOREX SWARM MIGRATION MASTER PLAN
**From Fragile Regex Bot to Autonomous Multi-Agent AI Swarm (Forex Edition)**

> **INSTRUCTION FOR OLLAMA / AI AGENT:** 
> Read this entire document. This is your "Prompt A to Prompt Z" architectural blueprint. Your task is to transform the legacy Forex telegram bot in `C:\anlyzeforex\Ai_forextele` into a State-of-the-Art, Crash-Proof, Multi-Agent Swarm OS. Execute this migration step-by-step exactly as outlined below.

---

## PHASE 1: The Core Threaded Architecture (Crash-Proofing)
The legacy system crashes because Telegram polling, execution, and UI are all in one loop. We must isolate them.

**Action Required:** Create `master_swarm_runner.py`
1. Build a class `SwarmThreadManager` that uses `subprocess` to launch isolated threads.
2. Thread 1: Telegram Listener (`telegram_signal_engine.py`).
3. Thread 2: Health Monitor (Checks system pulse, triggers Kill Switch if errors found).
4. Thread 3: WebSocket Bridge (`dashboard_websocket.py` running on port 8080).
5. Thread 4: End-of-Day GitHub Backup Scheduler (Runs daily at 23:55 to backup to git).

---

## PHASE 2: The Tri-Agent Swarm (Replacing Regex with AI)
Forex signals are notoriously messy ("Buy XAUUSD @ 2340 tp1 2345 tp2 2350 SL 2335... hold on update SL to entry"). Regex will fail. You must use Llama 3 for NLP.

**Action Required:** Create `swarm_engine.py` and `swarm_prompts.json`
1. **The Watcher Persona:** Analyzes raw forex Telegram text. Determines if it's a `NEW_TRADE`, an `UPDATE` (trailing SL), or `JUNK`.
2. **The Trigger Persona:** Extracts the exact symbol (e.g., XAUUSD, EURUSD), Action (BUY/SELL), Entry, SL, and multiple TPs (TP1, TP2, TP3) into strict JSON.
3. **The Governor Persona (FOREX RISK):**
   - **Pip Risk Limit:** Reject trades where the Stop Loss is greater than X pips (user-defined).
   - **R:R Ratio:** Strict minimum 1:2 Risk-to-Reward ratio.
   - **Multi-Target Logic:** If TP1 hits, mandate that the Stop Loss is immediately moved to Entry (Breakeven).
   - **Session Logic:** Forex trades 24/5. Ensure the time cutoff handles the Friday close/weekend gap appropriately.

---

## PHASE 3: Execution Handoff (MT5 / Forex Broker)
Instead of the Indian Dhan API, Forex requires MetaTrader 5 (MT5) or similar forex broker bridging.

**Action Required:** Update Execution Modules
1. Ensure `swarm_engine.py` imports the correct MT5 execution module (e.g., `real_mt5_execution.py`).
2. Map the AI's JSON output (Lots, Symbol, SL, TP) to the MT5 `OrderSend` format.
3. Ensure the Governor calculates Lot Size dynamically based on account balance and stop-loss pip distance (e.g., risking exactly 1% of equity per trade).

---

## PHASE 4: The React Live Dashboard (Visualizing the Swarm)
The user requires zero-latency visibility without static HTML refreshes.

**Action Required:** Build the Vite/React UI & WebSocket
1. Create `dashboard_websocket.py` to continuously read the backend `todays_report.json` and broadcast it to `ws://localhost:8080`.
2. Run `npx create-vite@latest dashboard_ui --template react`.
3. In `App.jsx`, implement a `WebSocket` connection to listen to port 8080.
4. Build a sleek, dark-mode Glassmorphism UI displaying:
   - **Forex Capital Base & Used Margin.**
   - **Active Positions Table** (Symbol, Entry, Live Price, Pips in Profit).
   - **Completed Trades** grouped by Telegram Channel.
   - **Live Debate Feed:** Auto-scrolling terminal showing The Watcher, Trigger, and Governor's internal thoughts.

---

## PHASE 5: Automated Testing & Backups (Zero-Touch OS)
The system must be fully hands-off and self-healing.

**Action Required:** Implement Automations
1. **GitHub Sync:** Create `eod_github_sync.py` that reads the daily PnL, asks Ollama to generate a commit message, and forcefully pushes the repository to GitHub at 23:55 every night.
2. **Institutional QA Testing Framework:** Create `run_institutional_test_suite.py`. This must be an automated script that feeds the entire Forex codebase back into Ollama, forcing it to act as an Institutional QA Engineer. The framework must automatically test for:
   - **Sanity & Regression:** Ensure the Telegram parsing and MT5 execution loops are intact.
   - **Code Quality & Calculation Bugs:** Specifically test the Forex pip math and lot-sizing logic in the Governor (preventing division-by-zero or negative return errors).
   - **Memory Leaks & Thread Safety:** Analyze `dashboard_websocket.py` to ensure closed React clients don't leak memory, and verify all Swarm threads are properly Daemonized.
   - Generate a detailed `SWARM_INSTITUTIONAL_QA_REPORT.md` every time this script runs.
3. **Master Boot Script:** Create `START_FOREX_SWARM.bat` that boots Ollama, starts the React dashboard, and launches `master_swarm_runner.py` with zero clicks. Schedule it via Windows Task Scheduler.

---
**FINAL AI DIRECTIVE:**
Do not hallucinate external libraries. Use `telethon` for Telegram and `MetaTrader5` (if applicable) for execution. Provide exact code replacements for each phase. Ensure all error handling gracefully degrades to the Health Monitor kill-switch. Begin Phase 1 immediately upon command.
