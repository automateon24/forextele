import asyncio
import httpx
import json
import logging
import csv
from datetime import datetime
from pathlib import Path
from real_mt5_execution import MT5ExecutionEngine
import MetaTrader5 as mt5

# ─── ML TRAINING DATA PATH ──────────────────────────────────────────────────
ML_TRAINING_FILE = Path(__file__).parent / "ml_training_data.csv"

def _log_ml_event(channel, symbol, action, entry, sl, tp, status, live_price_at_signal):
    """Append one row to the ML training CSV for post-hoc pattern learning."""
    file_exists = ML_TRAINING_FILE.exists()
    try:
        with open(ML_TRAINING_FILE, "a", newline='', encoding="utf-8") as f:
            w = csv.writer(f)
            if not file_exists:
                w.writerow(["timestamp","channel","symbol","action","entry","sl","tp",
                             "live_price_at_signal","price_deviation_pct","status"])
            dev = round(abs((float(entry)-float(live_price_at_signal))/float(live_price_at_signal))*100, 4) if entry and live_price_at_signal else None
            w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        channel, symbol, action, entry, sl, tp, live_price_at_signal, dev, status])
    except Exception as e:
        logging.getLogger(__name__).warning(f"[ML_LOG] Could not write training data: {e}")

BASE_DIR = Path(__file__).parent
PROMPTS_FILE = BASE_DIR / "swarm_prompts.json"

# ─── SPAM KEYWORD BLACKLIST (client-side, before Ollama) ────────────────────
SPAM_KEYWORDS = [
    "join fast", "join now", "join our", "vip today",
    "paid channel", "paid group", "subscribe", "click here",
    "whatsapp.com", "show me you active", "show me you're active",
    "message me", "contact me", "limited time",
    "lifetime subscription", "month subscription", "without money",
    "accuracy", "jackpot", "enjoy your profit", "tp hit", "tp1 hit",
    "tp2 hit", "tp3 hit", "pips profit", "pips jackpot", "ready?",
    "who is ready", "who is active", "are you active", "are you ready",
    "open a vip", "invite link", "invite you", "add you to",
    "don't miss", "dont miss", "act fast", "limited slots",
]

# ─── DAILY CIRCUIT BREAKER ──────────────────────────────────────────────────
MAX_DAILY_LOSS_PCT = 999.0 # Disabled for paper trading  # Stop ALL Telegram trades if account drops 3% today

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
            "format": "json",
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

        # ── GATE 0: Client-side spam keyword blacklist (before Ollama) ──────
        msg_lower = raw_message.lower()
        for kw in SPAM_KEYWORDS:
            if kw in msg_lower:
                log.info(f"[SPAM_GATE] Blocked by keyword '{kw}' — silently discarded.")
                return {"status": "REJECTED", "reason": f"Spam keyword: '{kw}'"}

        # ── GATE 1: Minimum length check ─────────────────────────────────────
        if len(raw_message.strip()) < 15:
            log.info("[SPAM_GATE] Message too short — discarded.")
            return {"status": "REJECTED", "reason": "Message too short"}

        # ── GATE 2: Daily circuit breaker ────────────────────────────────────
        try:
            if mt5.terminal_info():
                acc = mt5.account_info()
                if acc:
                    from datetime import timedelta
                    now = datetime.now()
                    yesterday = now - timedelta(hours=24)
                    deals = mt5.history_deals_get(yesterday, now)
                    if deals:
                        daily_pnl = sum(d.profit for d in deals if d.magic == 777777 and d.entry == mt5.DEAL_ENTRY_OUT)
                        daily_loss_pct = abs(daily_pnl) / acc.balance if daily_pnl < 0 else 0
                        if daily_loss_pct >= MAX_DAILY_LOSS_PCT:
                            log.warning(f"[CIRCUIT_BREAKER] Daily Telegram loss {daily_loss_pct:.1%} >= {MAX_DAILY_LOSS_PCT:.0%} limit. HALTING new Telegram trades.")
                            self._log_audit(account_id, channel_name, raw_message, {}, "REJECTED", f"Circuit breaker: daily loss {daily_loss_pct:.1%} exceeded {MAX_DAILY_LOSS_PCT:.0%} limit")
                            return {"status": "REJECTED", "reason": "Circuit breaker triggered"}
        except Exception as cb_ex:
            log.warning(f"[CIRCUIT_BREAKER] Could not check daily PnL: {cb_ex}")
        
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
            # Silently drop promotional spam without polluting the audit log
            return {"status": "REJECTED", "reason": "Classified as JUNK by Watcher"}
            
        if classification == "UPDATE":
            # Silently drop updates
            return {"status": "UPDATE_REQUIRED", "raw": raw_message}
            
        if classification != "NEW_TRADE":
            # Silently drop unknown formats
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
            # Log it so it appears in the UI table
            self._log_audit(account_id, channel_name, raw_message, {}, "FAILED", "Trigger could not parse a valid trade structure from this signal")
            return {"status": "FAILED", "reason": "Trigger hallucinated non-JSON output"}

        # 3. The Governor (Hardcoded Python Logic for 100% Reliability & Speed)
        log.info("[GOVERNOR] Evaluating Risk Profile...")
        
        entry = trade_data.get("entry")
        sl = trade_data.get("sl")
        tp1 = trade_data.get("tp1")
        
        if entry is None or (isinstance(entry, (int,float)) and float(entry) <= 0) or entry == "":
            # ── MARKET ORDER FALLBACK: no entry → execute at live market price ──
            log.info("[GOVERNOR] No entry price in signal — switching to MARKET execution")
            risk_decision = {"approved": True, "rejection_reason": "",
                             "entry_override": "MARKET",
                             "final_sl": 0.0, "final_tp1": 0.0,
                             "final_tp2": None, "final_tp3": None,
                             "risk_reward_ratio": 1.5}
            # Inject market as entry so the executor uses live price
            trade_data["entry"] = None
        else:
            entry = float(entry)
            symbol = trade_data.get("symbol", "").upper()
            action = trade_data.get("action", "BUY").upper()
            
            # Default ATR proxies if missing
            is_gold = "XAU" in symbol or "GOLD" in symbol
            atr_sl_dist = 10.0 if is_gold else 0.0050
            atr_tp_dist = 20.0 if is_gold else 0.0100
            
            sl = trade_data.get("sl")
            tp1 = trade_data.get("tp1")
            
            # Safe float conversion
            try:
                sl_val = float(sl) if sl is not None and sl != "" else 0.0
            except:
                sl_val = 0.0
                
            try:
                tp1_val = float(tp1) if tp1 is not None and tp1 != "" else 0.0
            except:
                tp1_val = 0.0
            
            if sl_val <= 0:
                log.info(f"[GOVERNOR] SL missing or invalid, auto-calculating ATR proxy for {symbol}")
                sl = entry - atr_sl_dist if "BUY" in action else entry + atr_sl_dist
            else:
                sl = sl_val
                
            if tp1_val <= 0:
                log.info(f"[GOVERNOR] TP missing or invalid, auto-calculating ATR proxy for {symbol}")
                tp1 = entry + atr_tp_dist if "BUY" in action else entry - atr_tp_dist
            else:
                tp1 = tp1_val
                
            risk_decision = {
                "approved": True,
                "rejection_reason": "",
                "final_sl": float(sl),
                "final_tp1": float(tp1),
                "final_tp2": trade_data.get("tp2"),
                "final_tp3": trade_data.get("tp3"),
                "risk_reward_ratio": 1.5
            }

        if not risk_decision.get("approved", False):
            log.warning(f"[GOVERNOR] VETOED TRADE! Reason: {risk_decision.get('rejection_reason')}")
            self._log_audit(account_id, channel_name, raw_message, trade_data, "REJECTED", risk_decision.get('rejection_reason'))
            return {"status": "REJECTED", "reason": risk_decision.get('rejection_reason')}
            
        log.info(f"[GOVERNOR] TRADE APPROVED! Final Parameters Set.")
        
        # Merge the Governor's calculated SL/TP with the Trigger's base data
        final_trade = {**trade_data, **risk_decision}
        final_trade["status"] = "APPROVED"
        final_trade["risk_modifier"] = risk_modifier

        # Hard-coded Broker specific overrides (Force AI compliance)
        if final_trade.get("symbol") in ["XAUUSD", "XAU", "XAU/USD"]:
            final_trade["symbol"] = "GOLD"

        # ── GATE 3: Price Sanity Check (blocks hallucinated prices) ─────────
        try:
            if mt5.terminal_info():
                symbol = final_trade.get("symbol", "")
                if mt5.symbol_select(symbol, True):
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        live_price = tick.ask if final_trade.get("action") == "BUY" else tick.bid
                        entry_price = final_trade.get("entry")
                        if entry_price and live_price and live_price > 0:
                            deviation_pct = abs(entry_price - live_price) / live_price
                            # Log to ML training data regardless of outcome
                            _log_ml_event(channel_name, symbol,
                                          final_trade.get("action"),
                                          entry_price, final_trade.get("final_sl"),
                                          final_trade.get("final_tp1"),
                                          "PASSED" if deviation_pct <= 0.15 else "PRICE_GATE_REJECT",
                                          live_price)
                            if deviation_pct > 0.15:  # Widened to 15% — covers crypto/gold swings
                                reason = f"Price sanity fail: entry {entry_price} is {deviation_pct:.1%} from live {live_price:.5f}"
                                log.warning(f"[PRICE_GATE] {reason}")
                                self._log_audit(account_id, channel_name, raw_message, final_trade, "REJECTED", reason)
                                return {"status": "REJECTED", "reason": reason}
        except Exception as pg_ex:
            log.warning(f"[PRICE_GATE] Could not validate price: {pg_ex}")
        
        # ── Symbol validation: let MT5 decide if unsupported — log for ML study
        symbol = final_trade.get("symbol", "").upper()
        base_asset = symbol.replace("USDT", "").replace("USD", "").replace("PERP", "")
        SUPPORTED = {"EUR","GBP","AUD","NZD","CAD","CHF","JPY","XAU","XAG",
                     "BTC","ETH","GOLD","SILVER","US30","NAS100","SP500","OIL",""}
        if base_asset not in SUPPORTED:
            # Don't hard-reject — log as ALTCOIN and let MT5 attempt execution
            # This feeds the ML training data on which exotic pairs ever succeed
            log.info(f"[SWARM_ENGINE] Altcoin '{base_asset}' detected — forwarding to MT5 for broker check")
            _log_ml_event(channel_name, symbol, final_trade.get("action"),
                          final_trade.get("entry"), final_trade.get("final_sl"),
                          final_trade.get("final_tp1"), "ALTCOIN_ATTEMPT", None)
        
        # --- PHASE 3: EXECUTION HANDOFF ---
        log.info("[HANDOFF] Routing payload to MT5 Broker...")
        try:
            short_chan = channel_name[:12].strip()
            final_trade["comment"] = f"Tele: {short_chan} 777777"
            success = self.mt5_engine.execute_trade(final_trade, magic_number=777777)
        except Exception as ex:
            log.error(f"[EXECUTION] Critical exception during MT5 handoff: {ex}")
            success = False
            
        exec_status = "SUCCESS" if success else "FAILED"
        exec_reason = "Trade executed successfully on MT5" if success else "MT5 execution failed — check broker logs"
        
        self._log_audit(account_id, channel_name, raw_message, final_trade, exec_status, exec_reason)
        
        final_trade["execution_status"] = exec_status
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
        
        # Always show parsed data if it exists, even if rejected
        action = parsed_data.get('action', '')
        symbol = parsed_data.get('symbol', '')
        entry = parsed_data.get('entry', '')
        
        parsed_str = f"{action} {symbol} @ {entry}" if symbol else "N/A"
        
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
            
        # Write to JSON log for Dashboard visibility
        json_log_file = BASE_DIR / "message_ai_log.json"
        try:
            logs = []
            if json_log_file.exists():
                with open(json_log_file, "r", encoding="utf-8") as jf:
                    logs = json.load(jf)
            
            # Keep only last 200 logs
            if len(logs) > 200:
                logs = logs[-200:]
                
            entry = {
                "channel_name": channel_name,
                "message": raw_message,
                "ai_reply": json.dumps(parsed_data) if parsed_data else '{"action": "NO_TRADE"}',
                "order_status": "Success" if status == "SUCCESS" else "Failed",
                "error_msg": reason if status != "SUCCESS" else None,
                "ticket": parsed_data.get("ticket", None) if parsed_data else None,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            logs.append(entry)
            
            with open(json_log_file, "w", encoding="utf-8") as jf:
                json.dump(logs, jf, indent=2)
        except Exception as e:
            log.error(f"Failed to write to JSON log: {e}")

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
