import asyncio
import httpx
import json
import logging
import csv
from datetime import datetime
from pathlib import Path
from real_mt5_execution import MT5ExecutionEngine

BASE_DIR = Path(__file__).parent
PROMPTS_FILE = BASE_DIR / "swarm_prompts.json"

log = logging.getLogger(__name__)

class OllamaSwarmEngine:
    def __init__(self, ollama_url="http://127.0.0.1:11434/api/generate", model="llama3.2"):
        self.ollama_url = ollama_url
        self.model = model
        self.mt5_engine = MT5ExecutionEngine()
        with open(PROMPTS_FILE, "r") as f:
            self.prompts = json.load(f)

    async def _ask_ollama(self, system_prompt: str, user_text: str) -> str:
        """Core communication layer with Ollama."""
        full_prompt = f"{system_prompt}\n\nUSER INPUT:\n{user_text}"
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.0 # Strict determinism for trading
            }
        }
        
        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                resp = await client.post(self.ollama_url, json=payload)
                resp.raise_for_status()
                return resp.json().get("response", "").strip()
            except Exception as e:
                log.error(f"Ollama API Error: {e}")
                return ""

    async def process_telegram_signal(self, raw_message: str, channel_name: str = "Unknown", account_id: str = "Unknown"):
        """
        The Master Tri-Agent Pipeline.
        Passes the message through Watcher -> Trigger -> Governor.
        """
        log.info("--- SWARM PIPELINE INITIATED ---")
        
        # 1. The Watcher
        watcher_resp = await self._ask_ollama(self.prompts["WATCHER_PROMPT"], raw_message)
        
        try:
            clean_watcher = watcher_resp.replace("```json", "").replace("```", "").strip()
            watcher_data = json.loads(clean_watcher)
            classification = watcher_data.get("classification", "UNKNOWN")
            risk_modifier = watcher_data.get("risk_modifier", 1.0)
            log.info(f"[WATCHER] Classified as: {classification} | Risk Modifier: {risk_modifier}x")
        except json.JSONDecodeError:
            log.error(f"[WATCHER] Failed to parse JSON: {watcher_resp}")
            return {"status": "FAILED"}
        
        if classification == "JUNK":
            self._log_audit(account_id, channel_name, raw_message, {}, "REJECTED", "Classified as JUNK by Watcher")
            return {"status": "REJECTED", "reason": "Classified as JUNK by Watcher"}
            
        if classification == "UPDATE":
            # Pass to an update handler (Phase 2 expansion)
            self._log_audit(account_id, channel_name, raw_message, {}, "UPDATE", "Signal is an update/closure")
            return {"status": "UPDATE_REQUIRED", "raw": raw_message}
            
        if classification != "NEW_TRADE":
            self._log_audit(account_id, channel_name, raw_message, {}, "REJECTED", "Watcher returned invalid classification")
            return {"status": "UNKNOWN", "reason": "Watcher returned invalid classification"}

        # 2. The Trigger
        log.info("[TRIGGER] Extracting trade data...")
        active_symbols = self.mt5_engine.get_available_symbols()
        symbols_context = f"\n\nBROKER AVAILABLE SYMBOLS: {', '.join(active_symbols)}"
        
        trigger_resp = await self._ask_ollama(self.prompts["TRIGGER_PROMPT"], raw_message + symbols_context)
        
        try:
            # Clean possible markdown from Ollama
            clean_json = trigger_resp.replace("```json", "").replace("```", "").strip()
            trade_data = json.loads(clean_json)
            log.info(f"[TRIGGER] Extraction Successful: {trade_data['action']} {trade_data['symbol']}")
        except json.JSONDecodeError:
            log.error(f"[TRIGGER] Failed to output valid JSON. Output: {trigger_resp}")
            self._log_audit(account_id, channel_name, raw_message, {}, "FAILED", "Trigger hallucinated non-JSON output")
            return {"status": "FAILED", "reason": "Trigger hallucinated non-JSON output"}

        # 3. The Governor
        log.info("[GOVERNOR] Evaluating Risk Profile...")
        governor_resp = await self._ask_ollama(self.prompts["GOVERNOR_PROMPT"], json.dumps(trade_data))
        
        try:
            clean_gov = governor_resp.replace("```json", "").replace("```", "").strip()
            risk_decision = json.loads(clean_gov)
        except json.JSONDecodeError:
            log.error(f"[GOVERNOR] Failed to output valid JSON. Output: {governor_resp}")
            self._log_audit(account_id, channel_name, raw_message, trade_data, "FAILED", "Governor hallucinated non-JSON output")
            return {"status": "FAILED", "reason": "Governor hallucinated non-JSON output"}

        if not risk_decision.get("approved", False):
            log.warning(f"[GOVERNOR] VETOED TRADE! Reason: {risk_decision.get('rejection_reason')}")
            self._log_audit(account_id, channel_name, raw_message, trade_data, "REJECTED", risk_decision.get('rejection_reason'))
            return {"status": "REJECTED", "reason": risk_decision.get('rejection_reason')}
            
        log.info(f"[GOVERNOR] TRADE APPROVED! Final Parameters Set.")
        
        # Merge the Governor's calculated SL/TP with the Trigger's base data
        final_trade = {**trade_data, **risk_decision}
        final_trade["status"] = "APPROVED"
        final_trade["risk_modifier"] = risk_modifier
        
        # Explicit Crypto Altcoin Block (Only allow BTC and ETH)
        symbol = final_trade.get("symbol", "").upper()
        base_asset = symbol.replace("USDT", "").replace("USD", "")
        if base_asset not in ["EUR", "GBP", "AUD", "NZD", "CAD", "CHF", "JPY", "XAU", "XAG", "BTC", "ETH", "GOLD", "SILVER", ""]:
            # If the base asset is not a major forex or BTC/ETH/Gold, reject it
            reason = f"Altcoin '{base_asset}' is not supported by this MT5 account. Only BTC and ETH are allowed."
            log.warning(f"[SWARM_ENGINE] VETO: {reason}")
            self._log_audit(account_id, channel_name, raw_message, trade_data, "REJECTED", reason)
            return {"status": "REJECTED", "reason": reason}
        
        # --- PHASE 3: EXECUTION HANDOFF ---
        log.info("[HANDOFF] Routing payload to MT5 Broker...")
        success = self.mt5_engine.execute_trade(final_trade)
        if success:
            final_trade["execution_status"] = "SUCCESS"
        else:
            final_trade["execution_status"] = "FAILED"
            
        self._log_audit(account_id, channel_name, raw_message, final_trade, "APPROVED", "Passed Watcher & Governor logic")
        return final_trade
        
    def _log_audit(self, account_id, channel_name, raw_message, parsed_data, status, reason):
        """Logs the final disposition of a signal to the audit CSV."""
        audit_file = BASE_DIR / "signals_audit.csv"
        file_exists = audit_file.exists()
        
        # Calculate today trade number
        trade_num = 1
        if file_exists:
            try:
                with open(audit_file, "r", encoding="utf-8") as f:
                    # just count lines for trade number
                    lines = f.readlines()
                    if len(lines) > 1:
                        trade_num = len(lines)
            except:
                pass
                
        # Clean raw message
        clean_raw = raw_message.replace('\n', ' ')[:150] + "..." if len(raw_message) > 150 else raw_message.replace('\n', ' ')
        parsed_str = f"{parsed_data.get('action', '')} {parsed_data.get('symbol', '')} @ {parsed_data.get('entry', '')}" if status == "APPROVED" else "N/A"
        
        with open(audit_file, "a", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Account", "Channel", "Raw_Signal", "Parsed_Signal", "Status", "Reason", "Trade_Number"])
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                account_id,
                channel_name,
                clean_raw,
                parsed_str,
                status,
                reason,
                trade_num
            ])

# Standalone test execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_msg = "XAUUSD BUY 4135.66\nSL: 4125.66\nTP1: 4145\nTP2: 4155\n--Trade by William"
    
    async def run_test():
        engine = OllamaSwarmEngine()
        result = await engine.process_telegram_signal(test_msg)
        print("\nFINAL PIPELINE RESULT:")
        print(json.dumps(result, indent=2))
        
    asyncio.run(run_test())
