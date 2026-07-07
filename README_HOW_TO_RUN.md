# AI Forex Master Engine - Standalone Deployment

Welcome to the new standalone branch of your algorithmic trading system. This folder contains only the essential core files needed to run the 24-channel Telegram Parser and the Machine Learning Strategy Engine.

## How to Run the System

1. Double-click the file named **`START_FOREX_SYSTEM.bat`** in this folder.
2. A single black console window will open.
3. It will automatically boot up all three core services in the background:
   - `dashboard_flask.py` (Local Web Server)
   - `live_order_executor.py` (Telegram Sniper)
   - `live_strategy_executor.py` (AI Autonomous Trader)
4. The console will display live aggregated logs from all three systems simultaneously so you can monitor them in one place.

## How to Access the Dashboard

Once the `.bat` file is running, open your web browser and navigate to:
**http://127.0.0.1:5000**

From here, you can view the system health heartbeat, watch active trades, and see algorithmic status in real-time.

## Notes for Development
- If you edit the code in this folder (`Ai_forextele`), it will NOT affect the old folder (`forextele`). You can safely experiment and test new features here.
- The Telegram session files (`.session`) have been migrated, so you do **not** need to scan QR codes or login with your phone numbers again!
- The MT5 login configuration and AI API keys are already pre-configured.

Enjoy trading!
