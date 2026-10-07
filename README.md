# 🚀 FOREXTELE: 24/7 AUTONOMOUS MULTI-ENGINE TRADING SUITE
**Target Asset:** Gold (`XAUUSD`) & Bitcoin (`BTCUSD`) | **Broker:** MetaTrader 5 (XM Global Direct)  
**Architecture:** 3 Autonomous Algorithmic Engines + 24/7 Reboot Supervisor + AI Learning Knowledge Base

---

## 📑 TABLE OF CONTENTS
1. [Quick Start & Launchers](#-quick-start--launchers)
2. [Program File Directory & Paths](#-program-file-directory--paths)
3. [Engine 1: BreakoutBoss v2 (Multi-Session + Gann)](#-engine-1-breakoutboss-v2)
4. [Engine 2: Autonomous SMC AI Market Scanner](#-engine-2-autonomous-smc-ai-market-scanner)
5. [Engine 3: Telegram VIP Signal Swarm Engine](#-engine-3-telegram-vip-signal-swarm-engine)
6. [24/7 Persistence, Watchdog & Reboot Recovery](#-247-persistence-watchdog--reboot-recovery)
7. [AI Trade Learning & Daily Auto-Tune](#-ai-trade-learning--daily-auto-tune)
8. [Live Logs, Audits & Ledgers](#-live-logs-audits--ledgers)

---

## ⚡ QUICK START & LAUNCHERS

| Action | File Path | Description |
| :--- | :--- | :--- |
| **Start 24/7 Suite + Live HUD** | [`START_247_PERSISTENT_SUITE.bat`](file:///c:/anlyzeforex/forextele/START_247_PERSISTENT_SUITE.bat) | Fresh start: terminates prior threads cleanly, ensures boot persistence, launches engines, and opens live HUD monitor. |
| **Restart All Engines** | [`RESTART_ALL_ENGINES.bat`](file:///c:/anlyzeforex/forextele/RESTART_ALL_ENGINES.bat) | Clean restart script that reloads all parameters and brings up the live monitor. |
| **Stop All Engines** | [`STOP_ALL_ENGINES.bat`](file:///c:/anlyzeforex/forextele/STOP_ALL_ENGINES.bat) | Force-terminates all engines and closes open positions. |
| **Consolidated Live Monitor** | [`consolidated_live_suite.py`](file:///c:/anlyzeforex/forextele/consolidated_live_suite.py) | Python live console aggregator with account metrics, engine status, and filtered real-time event stream. |

---

## 📁 PROGRAM FILE DIRECTORY & PATHS

### 1. Master Engines (Core Algorithmic Scripts)
- **BreakoutBoss v2:** [`c:\anlyzeforex\forextele\breakout_boss_engine.py`](file:///c:/anlyzeforex/forextele/breakout_boss_engine.py)  
  *5 compounding models, 6 global session breakouts, Gann timing candle #72, dynamic quote anchoring, and two-stage TSL.*
- **Autonomous SMC AI Scanner:** [`c:\anlyzeforex\forextele\autonomous_ai_market_scanner.py`](file:///c:/anlyzeforex/forextele/autonomous_ai_market_scanner.py)  
  *Institutional M15 Fair Value Gap (FVG) and Liquidity Sweep scanner for Gold & BTCUSD.*
- **Telegram Signal Swarm Engine:** [`c:\anlyzeforex\forextele\telegram_signal_engine.py`](file:///c:/anlyzeforex/forextele/telegram_signal_engine.py)  
  *Telethon client listening to 40+ VIP channels with dual-account replication.*
- **Swarm AI Parsing & Conviction Gate:** [`c:\anlyzeforex\forextele\swarm_engine.py`](file:///c:/anlyzeforex/forextele/swarm_engine.py)  
  *Ollama LLM trade extractor with Option 2 Strict Conviction Gate (`>= 0.85`) and Macro H1 trend confluence.*
- **Market Trader Engine:** [`c:\anlyzeforex\forextele\market_trader_engine.py`](file:///c:/anlyzeforex/forextele/market_trader_engine.py)  
  *Dedicated parser for Market Trader Crypto Forex (Magic: `888888`).*
- **Real MT5 Execution Engine:** [`c:\anlyzeforex\forextele\real_mt5_execution.py`](file:///c:/anlyzeforex/forextele/real_mt5_execution.py)  
  *Direct MetaTrader 5 order execution, price sanitization, and lot sizing safety caps.*
- **AI Conviction Dynamic TSL Manager:** [`c:\anlyzeforex\forextele\ai_conviction_tsl_manager.py`](file:///c:/anlyzeforex/forextele/ai_conviction_tsl_manager.py)  
  *Real-time tick trailing stop manager and channel conviction database.*

### 2. Supervisors & 24/7 Watchdogs
- **Master Autostart Watchdog:** [`c:\anlyzeforex\forextele\master_autostart_watchdog.py`](file:///c:/anlyzeforex/forextele/master_autostart_watchdog.py)  
  *Monitors every 60s, restarts dropped engines, launches MT5 if missing, holds socket port 39888.*
- **Persistent Watchdog Launcher:** [`c:\anlyzeforex\forextele\start_watchdog_persistent.py`](file:///c:/anlyzeforex/forextele/start_watchdog_persistent.py)  
  *Detached Windows daemon launcher invoked on system boot.*
- **AI Backtest Alignment Supervisor:** [`c:\anlyzeforex\forextele\ai_backtest_alignment_watchdog.py`](file:///c:/anlyzeforex/forextele/ai_backtest_alignment_watchdog.py)  
  *Evaluates live engine win rates against 1-month backtest benchmarks; auto-throttles risk if divergent.*

### 3. AI Learning & Reinforcement Models
- **AI Trade Learning Engine:** [`c:\anlyzeforex\forextele\ai_trade_learning_engine.py`](file:///c:/anlyzeforex/forextele/ai_trade_learning_engine.py)  
  *Reverse-engineers live market context (FVG, sweeps, RSI, trend) for every trade.*
- **Live ML Reinforcement Learner:** [`c:\anlyzeforex\forextele\ml_reinforcement_learner.py`](file:///c:/anlyzeforex/forextele/ml_reinforcement_learner.py)  
  *Online incremental retraining of trade weights.*
- **Learned Channel Profiles & Rules:** [`c:\anlyzeforex\forextele\data\channel_archetypes_and_rules.json`](file:///c:/anlyzeforex/forextele/data/channel_archetypes_and_rules.json)  
  *Win rates, net P&L, and top SMC patterns across all monitored channels.*
- **Trade Learning Knowledge Base (JSONL):** [`c:\anlyzeforex\forextele\data\trade_learning_knowledge_base.jsonl`](file:///c:/anlyzeforex/forextele/data/trade_learning_knowledge_base.jsonl)  
  *1,000+ empirical trades logged with SMC market context and outcomes.*

---

## 🎯 ENGINE 1: BREAKOUTBOSS v2

Complete standalone reference: [`c:\anlyzeforex\forextele\BREAKOUT_BOSS_SPECIFICATION.md`](file:///c:/anlyzeforex/forextele/BREAKOUT_BOSS_SPECIFICATION.md)

### Key Rules & Architecture:
1. **Target Asset:** `GOLD` (XAUUSD).
2. **Total Allocation:** `$5,000 USD` across 5 virtual compounding baskets ($1,000 each).
3. **Session Safeguard:** **Maximum 1 trade setup per session per day** (eliminates multi-timeframe stacking).
4. **Volatility Compression Gate:** Opening reference range ($R_{\text{ref}}$) must be between $\$0.35$ and the timeframe volatility cap ($3.50 for M1, $6.50 for M5).
5. **Macro H1 Trend Filter:**
   - H1 BEARISH $\to$ ONLY SELL setups allowed.
   - H1 BULLISH $\to$ ONLY BUY setups allowed.
6. **Retest & Rejection Confirmation:** Does NOT enter on blind breakout. Price must pull back to touch the breakout level within $\$0.25$ and print a rejection candle.
7. **Two-Stage TSL:**
   - At $+1.5\text{R}$ profit $\to$ Move SL to Entry $+\$0.20$ (Breakeven Locked).
   - Past $+2.5\text{R}$ profit $\to$ Trail market price at $1.5\text{R}$ distance in $\$0.30$ steps.
8. **EOD Force-Close:** All open trades closed at `20:50 UTC` (03:20 AM IST) before market rollover.

### Global Sessions Schedule:
- **ASIA (Asian Open):** `01:00 UTC` (06:30 AM IST) | M1 only | Target R:R 1:1.5
- **FRA (Frankfurt Open):** `06:00 UTC` (11:30 AM IST) | M1 (1:5.0 R:R), M5 (1:3.0 R:R) | **#1 Session Worldwide (76.9% WR, 9.21 PF)**
- **LON (London Core):** `08:00 UTC` (01:30 PM IST) | M1 (1:3.0 R:R), M5 (1:3.0 R:R) | 86.7% WR
- **NYP (NY Pre-Market):** `12:30 UTC` (06:00 PM IST) | M1 (1:3.0 R:R), M5 (1:3.0 R:R) | US Macro news expansion
- **NYC (NY Cash Open):** `13:30 UTC` (07:00 PM IST) | M1 (1:5.0 R:R), M5 (1:3.0 R:R) | 92.3% WR
- **LNC (London Close):** `15:30 UTC` (09:00 PM IST) | M1 only | Target R:R 1:3.0

### W.D. Gann Harmonic Timing Cycle:
- **Candle #72:** 72nd 1-minute candle of the day (~`02:11 UTC` / `07:41 AM IST`).
  - Coincides with the Tokyo Liquidity Acceleration & Asian Half-Cycle harmonic.
  - Breakout & retest executed at **1:1.5 R:R** with a 1.10x conviction multiplier.

### The 5 Compounding Models:
- **M0 (Magic `555000`):** Fixed 0.02 Lots (Strategy baseline benchmark).
- **M1 (Magic `555001`):** Milestone Step-Ladder (0.02 $\to$ 0.10 lots based on virtual equity tiers).
- **M2 (Magic `555002`):** Linear Equity Dynamic ($\text{Lots} = \text{Equity}/1000 \times 0.02$).
- **M3 (Magic `555003`):** AI Conviction Weighted (Frankfurt 1.35x, NYC 1.15x, Tokyo 0.70x).
- **M4 (Magic `555004`):** Aggressive Half-Kelly Growth ($\text{Lots} = \text{Equity}/1000 \times 0.03$).

---

## 🤖 ENGINE 2: AUTONOMOUS SMC AI MARKET SCANNER
**Script:** [`c:\anlyzeforex\forextele\autonomous_ai_market_scanner.py`](file:///c:/anlyzeforex/forextele/autonomous_ai_market_scanner.py) | **Magic:** `999001`

- **Symbols:** `GOLD` and `BTCUSD`.
- **Methodology:** Institutional Smart Money Concepts (M15 Fair Value Gaps + Liquidity Sweeps).
- **Execution Rules:**
  - In H1 BEARISH trend $\to$ Only sells M15 Bearish FVG mitigations.
  - In H1 BULLISH trend $\to$ Only buys M15 Bullish FVG mitigations.
  - In NEUTRAL trend $\to$ Enforces extreme RSI ($<28$ or $>72$) at psychological round numbers.
- **BTCUSD Volatility Gate:** Requires M15 ATR $\ge 3.5\times \text{Spread}$ to avoid chop drag.
- **Daily Limit:** Max 4 autonomous trades per UTC day with automatic cooldown scaling.

---

## 📱 ENGINE 3: TELEGRAM VIP SIGNAL SWARM ENGINE
**Script:** [`c:\anlyzeforex\forextele\telegram_signal_engine.py`](file:///c:/anlyzeforex/forextele/telegram_signal_engine.py) | **Magic:** `777777` (Acct 1) / `888001` (Acct 2)

- **Channels Monitored:** 40+ VIP Telegram channels via Telethon.
- **Option 2 Strict Conviction Gate (`>= 0.85`):**
  - All signals from channels with conviction $< 0.85$ are **100% blocked and rejected**.
  - **Whitelisted Elite Channels:** `Swich Gold Forex` (0.95), `Market Trader` (0.92), `Perfect Management` (0.90), `Josefina Trader` (0.88), `Forex with Karol` (0.88), `Gold VIP` (0.85).
- **Trend Confluence:** Any signal calling counter-trend trades into an H1 EMA trend is vetoed.
- **Hard Safety Lot Cap:** Volume strictly capped at **0.04 lots maximum** in [real_mt5_execution.py](file:///c:/anlyzeforex/forextele/real_mt5_execution.py) (preventing oversized drawdown).

---

## 🛡️ 24/7 PERSISTENCE, WATCHDOG & REBOOT RECOVERY

The suite is engineered to run continuously for **1 month** without interruption:

1. **Windows Task Scheduler (System Boot):**
   - Task Name: `Forextele_Boot_AutoStart`
   - Trigger: System startup (`/SC ONSTART`) under `SYSTEM` with highest privileges.
   - Automatically recovers and launches all engines if the VPS restarts for updates.
2. **Watchdog Supervisor Task:**
   - Task Name: `Forextele_247_Persistent_Watchdog`
   - Trigger: Repeats every 5 minutes (`/SC MINUTE /MO 5`).
3. **Master Watchdog Daemon:**
   - Script: [`master_autostart_watchdog.py`](file:///c:/anlyzeforex/forextele/master_autostart_watchdog.py)
   - Checks every 60s: MT5 Terminal, BreakoutBoss, SMC AI Scanner, Telegram Signal Engine.
   - Self-heals and relaunches any crashed or dropped process.
   - Strictly isolates from and **never touches `C:\SepPro` or `C:\Auguspro`**.

---

## 📊 LIVE LOGS, AUDITS & LEDGERS

All operational data is stored in [`c:\anlyzeforex\forextele\logs\`](file:///c:/anlyzeforex/forextele/logs/) and [`c:\anlyzeforex\forextele\data\`](file:///c:/anlyzeforex/forextele/data/):

| Purpose | File Path |
| :--- | :--- |
| **BreakoutBoss Activity Log** | [`logs/breakout_boss.log`](file:///c:/anlyzeforex/forextele/logs/breakout_boss.log) |
| **SMC Scanner Activity Log** | [`logs/smc_scanner.log`](file:///c:/anlyzeforex/forextele/logs/smc_scanner.log) |
| **Telegram Signals Activity Log** | [`logs/telegram_signals.log`](file:///c:/anlyzeforex/forextele/logs/telegram_signals.log) |
| **Master Watchdog Health Log** | [`logs/master_autostart_watchdog.log`](file:///c:/anlyzeforex/forextele/logs/master_autostart_watchdog.log) |
| **AI Backtest Alignment Log** | [`logs/ai_watchdog.log`](file:///c:/anlyzeforex/forextele/logs/ai_watchdog.log) |
| **Dynamic TSL Ratchet Log** | [`logs/tsl_manager.log`](file:///c:/anlyzeforex/forextele/logs/tsl_manager.log) |
| **Live AI Alignment Status** | [`live_ai_alignment_status.json`](file:///c:/anlyzeforex/forextele/live_ai_alignment_status.json) |
| **Active Trade Registry** | [`active_trades_registry.json`](file:///c:/anlyzeforex/forextele/active_trades_registry.json) |
| **Audit CSV of Intercepted Signals**| [`signals_audit.csv`](file:///c:/anlyzeforex/forextele/signals_audit.csv) |
