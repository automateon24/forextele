import logging
import json
import MetaTrader5 as mt5
import asyncio
import httpx
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [QA_FRAMEWORK] - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"
PROMPTS_FILE = BASE_DIR / "swarm_prompts.json"

class ForexQAFramework:
    def __init__(self):
        self.failed_tests = 0
        self.passed_tests = 0
        
    def _assert(self, condition, test_name, error_msg):
        if condition:
            log.info(f"✅ PASSED: {test_name}")
            self.passed_tests += 1
        else:
            log.error(f"❌ FAILED: {test_name} - {error_msg}")
            self.failed_tests += 1

    def test_mt5_connectivity(self):
        log.info("--- Running MT5 Connectivity Test ---")
        try:
            with open(MT5_CFG_PATH, "r") as f:
                cfg = json.load(f)
            
            init = mt5.initialize(login=int(cfg["login"]), server=cfg["server"], password=cfg["password"])
            self._assert(init, "MT5 Initialization", "Could not connect to broker.")
            
            acc = mt5.account_info()
            self._assert(acc is not None, "MT5 Account Info", "Could not fetch account details.")
            if acc:
                log.info(f"Account Equity: {acc.equity} | Balance: {acc.balance}")
        except Exception as e:
            self._assert(False, "MT5 Initialization", f"Exception: {e}")

    def test_market_structure_data(self):
        log.info("--- Running Market Structure Data Test ---")
        symbol = "GOLD"
        tick = mt5.symbol_info_tick(symbol)
        self._assert(tick is not None, f"Fetch Current Price for {symbol}", "Could not get live tick.")
        
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 2)
        self._assert(rates is not None and len(rates) > 0, f"Fetch Daily High/Low for {symbol}", "Could not get historical daily rates.")
        if rates is not None and len(rates) > 0:
            daily_high = rates[-1]['high']
            daily_low = rates[-1]['low']
            log.info(f"{symbol} Daily High: {daily_high} | Daily Low: {daily_low}")

    async def test_ollama_ai_engine(self):
        log.info("--- Running Ollama AI Parsing Test ---")
        try:
            with open(PROMPTS_FILE, "r") as f:
                prompts = json.load(f)
            
            trigger_prompt = prompts.get("TRIGGER_PROMPT", "")
            test_signal = "BUY GOLD NOW AT 2400 TP 2410 SL 2390"
            full_prompt = f"{trigger_prompt}\n\nExtract this: {test_signal}"
            
            payload = {
                "model": "llama3.2",
                "prompt": full_prompt,
                "stream": False,
                "options": {"temperature": 0.0}
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post("http://127.0.0.1:11434/api/generate", json=payload)
                resp.raise_for_status()
                result = resp.json().get("response", "").strip()
                
                try:
                    parsed_json = json.loads(result)
                    self._assert(parsed_json.get("symbol") == "GOLD", "AI Parsed Symbol", f"Expected GOLD, got {parsed_json.get('symbol')}")
                    self._assert(parsed_json.get("action") == "BUY", "AI Parsed Action", f"Expected BUY, got {parsed_json.get('action')}")
                except json.JSONDecodeError:
                    self._assert(False, "AI JSON Validation", f"Ollama did not return strict JSON. Got: {result}")
                    
        except Exception as e:
            import traceback
            log.error(traceback.format_exc())
            self._assert(False, "Ollama API Check", f"Exception: {e}")

    def test_algorithmic_forex_engine(self):
        log.info("--- Running Phase 1 Algorithmic Engine Test ---")
        try:
            import sys
            import os
            sys.path.append(str(BASE_DIR))
            from algorithmic_forex_engine import ForexAlgorithmicEngine
            engine = ForexAlgorithmicEngine()
            
            self._assert(len(engine.dna) > 0, "Load Strategy DNA", "Could not load strategy_dna.json")
            
            signals = engine.scan_market()
            self._assert(isinstance(signals, list), "Market Scanning Execution", "Did not return a list of signals")
            
            if len(signals) > 0:
                log.info(f"Test Signal Generated: {signals[0]}")
            else:
                log.info("No active setups found right now, but scan completed successfully.")
                
        except Exception as e:
            import traceback
            log.error(traceback.format_exc())
            self._assert(False, "Algorithmic Engine Test", f"Exception: {e}")

    def test_execution_pipeline(self):
        log.info("--- Running Phase 2 Execution Pipeline Test ---")
        try:
            import sys
            sys.path.append(str(BASE_DIR))
            from real_mt5_execution import MT5ExecutionEngine
            executor = MT5ExecutionEngine()
            self._assert(executor.connect(), "MT5 Executor Connection", "Executor failed to bind to MT5")
            
            # We don't place a real trade, just verify the lot size calculator which handles the V-Shape defense logic
            volume = executor.calculate_lot_size("GOLD", 2400.00, 2390.00, 0.01)
            self._assert(volume > 0, "Algorithmic Risk Scaler", f"Expected valid lot size, got {volume}")
            
        except Exception as e:
            self._assert(False, "Execution Pipeline Test", f"Exception: {e}")

    def test_dual_core_threads(self):
        log.info("--- Running Phase 3 Dual-Core Thread Test ---")
        import psutil
        telegram_running = False
        algo_running = False
        
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline:
                    cmd_str = ' '.join(cmdline).lower()
                    if 'telegram_signal_engine.py' in cmd_str:
                        telegram_running = True
                    if 'algorithmic_forex_engine.py' in cmd_str:
                        algo_running = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        self._assert(telegram_running, "Telegram Core Online", "The Telegram Sentinel is not running in background.")
        self._assert(algo_running, "Algo Core Online", "The 41/45 Strategy Engine is not running in background.")

    def run_all(self):
        log.info("==========================================")
        log.info("STARTING FOREX INSTITUTIONAL QA TEST SUITE")
        log.info("==========================================")
        self.test_mt5_connectivity()
        if mt5.terminal_info():
            self.test_market_structure_data()
            self.test_algorithmic_forex_engine()
            self.test_execution_pipeline()
        
        asyncio.run(self.test_ollama_ai_engine())
        
        self.test_dual_core_threads()
        
        log.info("==========================================")
        log.info(f"QA COMPLETE. Passed: {self.passed_tests} | Failed: {self.failed_tests}")
        if self.failed_tests > 0:
            log.warning("⚠️ QA SUITE FAILED. Do not proceed to Phase 1 until resolved.")
        else:
            log.info("✅ QA SUITE PASSED. System is ready for Phase 1.")
            
        mt5.shutdown()

if __name__ == "__main__":
    qa = ForexQAFramework()
    qa.run_all()
