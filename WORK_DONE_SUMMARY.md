# 🚀 Forex Swarm OS v2 — Work Done & Progress Summary

## 📌 Project Overview
This repository (`forextele`) houses the **Autonomous Multi-Agent Forex & Crypto Trading Swarm OS v2**. The system parses unstructured signals from Telegram channels via AI (Ollama Llama 3), passes them through a Tri-Agent risk governor, executes orders directly on MetaTrader 5 (MT5), and broadcasts real-time telemetry to a modern React Glassmorphism Dashboard.

---

## 🛠️ Key Milestones & Features Implemented

### 1. 🏗️ Tri-Agent Swarm OS Architecture (`master_swarm_runner.py`)
- **Multi-Threaded Subprocess Manager:** Isolates execution threads to prevent main-loop crashes:
  - **Thread 1:** Telegram Signal Listener (`telegram_signal_engine.py`)
  - **Thread 2:** System Health Monitor & Process Watchdog
  - **Thread 3:** WebSocket Telemetry Server (`dashboard_websocket.py` on port 8888)
  - **Thread 4:** Automated EOD GitHub Backup Scheduler

### 2. 🧠 AI Signal Parsing (Watcher -> Trigger -> Governor)
- **The Watcher:** Classifies raw Telegram posts into `NEW_TRADE`, `UPDATE`, or `JUNK`.
- **The Trigger:** Extracts symbol, action (BUY/SELL), entry, SL, and multiple targets into structured JSON.
- **The Governor:** Validates price sanity, Risk:Reward ratio ($\ge 1.5$), ATR stop fallbacks, and lot sizing.

### 3. 🛡️ Capital Protection & Hard 1.00 Lot Cap
- **Hard Max Lot Governor (`1.00 Lot Cap`):** Enforced a strict maximum upper bound of `1.00 Lot` across all dynamic lot calculation formulas and order placement functions in `real_mt5_execution.py` and `live_order_executor.py`.
- **Prevented Account Drain:** Stops runaway volume scaling on crypto/indices (e.g. ETHUSD, Gold) caused by small point distance values.
- **Position Cleanup:** Successfully closed out previous oversized positions (8.57 and 8.38 lots on ETHUSD).

### 4. 🌐 React Glassmorphism Dashboard UI
- **Frontend Stack:** Vite + React UI running on port `5555` ([http://localhost:5555](http://localhost:5555)).
- **WebSocket Bridge:** Real-time bi-directional telemetry broadcast on port `8888` (`ws://localhost:8888`).
- **Network Compatibility:** Configured `--host 0.0.0.0` binding for IPv4 & IPv6 localhost resolution.

### 5. 🤖 Machine Learning Pattern Logging (Walk-Forward Learning)
- **Demo Unrestricted Mode:** Circuit breaker (`MAX_DAILY_LOSS_PCT`) remains disabled (`999.0`) to maximize empirical trade data gathering.
- **Telemetry Logging:** All signals, entry prices, SL/TP levels, live price deviations, and outcomes are continuously appended to `ml_training_data.csv` and `master_trade_ledger.csv`.
- **ML Retraining (`ml_walkforward_trainer.py`):** Trains walk-forward classifiers (`second_model_sucess.joblib`) to continuously refine signal win-probability filters.

---

## 📁 Core Repository Structure

```
forextele/
├── master_swarm_runner.py          # Master multi-thread process orchestrator
├── swarm_engine.py                 # Tri-Agent (Watcher, Trigger, Governor) logic
├── telegram_signal_engine.py       # Telegram channel listener via Telethon
├── real_mt5_execution.py           # MT5 broker connection & order execution engine
├── live_order_executor.py          # Live order management & safety lot capping
├── dashboard_websocket.py          # WebSocket bridge server (port 8888)
├── dashboard_ui/                   # React Glassmorphism dashboard frontend (port 5555)
├── ml_walkforward_trainer.py       # Machine Learning training & evaluation script
├── START_SWARM_OS.bat              # One-click system boot script
└── WORK_DONE_SUMMARY.md            # Comprehensive project status & documentation
```

---

## 🚀 Quick Start Instructions

To launch the complete system (Backend Swarm + React Dashboard):

```cmd
C:\anlyzeforex\forextele\START_SWARM_OS.bat
```

- **Dashboard UI:** [http://localhost:5555](http://localhost:5555)
- **WebSocket Server:** `ws://localhost:8888`
