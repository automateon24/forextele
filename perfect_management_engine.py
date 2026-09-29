import re
import logging
import csv
from datetime import datetime
from pathlib import Path
import MetaTrader5 as mt5
from real_mt5_execution import MT5ExecutionEngine
from ai_conviction_tsl_manager import register_trade
from ai_trade_learning_engine import learning_engine

BASE_DIR = Path(__file__).parent
AUDIT_FILE = BASE_DIR / "signals_audit.csv"

log = logging.getLogger("PERFECT_MGT")

class PerfectManagementHandler:
    def __init__(self, mt5_engine: MT5ExecutionEngine = None):
        self.mt5_engine = mt5_engine or MT5ExecutionEngine()
        self.magic_number = 786786  # Dedicated Magic for Perfect Management (Independent from 888888)

    def _log_audit(self, action: str, symbol: str, entry: float, sl: float, tp: float, status: str, reason: str, raw_msg: str):
        file_exists = AUDIT_FILE.exists()
        try:
            with open(AUDIT_FILE, "a", newline='', encoding="utf-8") as f:
                w = csv.writer(f)
                if not file_exists:
                    w.writerow(["Timestamp", "Account", "Channel", "Raw_Signal", "Parsed_Signal", "Action", "Symbol", "Price", "SL", "TP", "Status", "Reason"])
                w.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Account 2",
                    "Perfect Management",
                    raw_msg.replace('\n', ' ')[:100],
                    f"{action} {symbol} @ {entry} (SL: {sl}, TP: {tp})",
                    action,
                    symbol,
                    entry,
                    sl,
                    tp,
                    status,
                    reason
                ])
        except Exception as e:
            log.warning(f"Could not log audit: {e}")

    async def handle_message(self, text: str, msg_id: int = None, reply_to_msg_id: int = None) -> dict:
        """
        Parses and executes Perfect Management Gold and BTCUSD signals with multi-tier TSL,
        active close commands, and volatility spread protection.
        """
        clean = text.replace('**', ' ').replace('*', ' ').strip()
        if not clean:
            return {"status": "SKIPPED", "reason": "Empty message"}

        clean_lower = clean.lower()

        # ── 1. Check for Active Close Commands ('Close now xauusd', 'Exit now') ──
        if re.search(r'\b(?:close\s+now|exit\s+now|close\s+xauusd)\b', clean_lower):
            log.info(f"[PERFECT_MGT] 🚨 Intercepted 'CLOSE NOW' command: {clean[:60]}")
            closed_ok = self.mt5_engine.close_position("GOLD", self.magic_number)
            self._log_audit("CLOSE_NOW", "GOLD", 0, 0, 0, "SUCCESS" if closed_ok else "NO_OPEN_ORDER", "Close command from channel", clean)
            return {"status": "PROCESSED", "action": "CLOSE_NOW", "symbol": "GOLD"}

        # ── 2. Check for Target Hit Commands ('TP¹ HIT DONE' vs 'TP² HIT DONE') ──
        if re.search(r'\b(?:tp[¹1]|target\s*1)\s*hit\s*done\b', clean_lower):
            log.info(f"[PERFECT_MGT] 🎯 TP1 Hit noted -> Keeping SL FIXED to let runner reach TP2: {clean[:60]}")
            self._log_audit("TP1_HIT", "GOLD", 0, 0, 0, "SUCCESS", "TP1 Hit -> Kept SL Fixed for TP2", clean)
            return {"status": "PROCESSED", "action": "TP1_HIT_HOLD", "symbol": "GOLD"}

        if re.search(r'\b(?:tp[²2]|target\s*2)\s*hit\s*done\b', clean_lower):
            log.info(f"[PERFECT_MGT] 🎯 TP2 Hit noted -> Putting TSL at TP2 & engaging 10-pip jumping TSL: {clean[:60]}")
            from ai_conviction_tsl_manager import activate_extension_tsl
            tsl_ok = activate_extension_tsl("GOLD", magic_number=self.magic_number, step_pips=10.0)
            self._log_audit("TP2_HIT", "GOLD", 0, 0, 0, "SUCCESS" if tsl_ok else "NO_OPEN_ORDER", "TP2 Hit -> Put TSL at TP2 + 10-pip trail", clean)
            return {"status": "PROCESSED", "action": "TP2_HIT_LOCK", "symbol": "GOLD"}

        # ── 3. Check for Massive Target / All TPs Hit ('All TP⁶ HIT DONE') ──
        if "all tp" in clean_lower and "hit" in clean_lower:
            log.info(f"[PERFECT_MGT] 💰 ALL TPs HIT DONE -> Booking 80% volume & locking profits: {clean[:60]}")
            pc_ok = self.mt5_engine.close_partial_position("GOLD", close_pct=80, magic_number=self.magic_number)
            self.mt5_engine.move_sl_to_breakeven("GOLD", self.magic_number)
            self._log_audit("BOOK_PROFIT_80%", "GOLD", 0, 0, 0, "SUCCESS" if pc_ok else "NO_OPEN_ORDER", "All TPs hit -> Booked 80%", clean)
            return {"status": "PROCESSED", "action": "BOOK_80%", "symbol": "GOLD"}

        # ── 4. Check for New Trade Entry Signal ──
        # Matches: #XAUUSD BUY 4352, BTCUSD SELL 81320, BTC BUY 81000, etc.
        sig_match = re.search(
            r'(?:#)?(XAUUSD|GOLD|BTCUSD|BTC|ETHUSD|ETH|US30|EURUSD|GBPUSD|USDJPY|GBPJPY|AUDUSD)\s+(BUY|SELL)\s+([0-9]+(?:\.[0-9]+)?)',
            clean,
            re.IGNORECASE
        )
        if not sig_match:
            return {"status": "IGNORED", "reason": "No actionable trade structure"}

        raw_sym = sig_match.group(1).upper()
        action = sig_match.group(2).upper()
        entry_price = float(sig_match.group(3))
        
        # Standardize symbol for broker
        if raw_sym in ("XAUUSD", "GOLD"):
            symbol = "GOLD"
        elif raw_sym in ("BTC", "BTCUSDT"):
            symbol = "BTCUSD"
        elif raw_sym in ("ETH", "ETHUSDT"):
            symbol = "ETHUSD"
        elif raw_sym in ("US30", "DJ30"):
            symbol = "US30Cash"
        else:
            symbol = raw_sym

        # Stop Loss
        sl_m = re.search(r'(?:SL|Sl|SI|Si|Stop\s*Loss)\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)', clean, re.IGNORECASE)
        sl_price = float(sl_m.group(1)) if sl_m else None

        # Multi-TP targets
        tp_pattern = r'(?:[¹²³⁴⁵⁶1-6]TP|TP[¹²³⁴⁵⁶1-6]|TARGET\s*[1-6]|TP)\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)'
        tp_matches = re.findall(tp_pattern, clean, re.IGNORECASE)
        tp_list = [float(v) for v in tp_matches]

        seen = set()
        dedup_tps = []
        for t in tp_list:
            if t not in seen:
                seen.add(t)
                dedup_tps.append(t)

        if action == "BUY":
            dedup_tps = sorted(dedup_tps)
        else:
            dedup_tps = sorted(dedup_tps, reverse=True)

        if not dedup_tps:
            dedup_tps = [entry_price + 10.0 if action == "BUY" else entry_price - 10.0]

        max_tp = dedup_tps[-1]

        if not self.mt5_engine.connected:
            self.mt5_engine.connect()

        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
        if not info:
            log.error(f"[PERFECT_MGT] Symbol {symbol} not found on broker!")
            return {"status": "ERROR", "reason": f"Symbol {symbol} unavailable"}

        tick = mt5.symbol_info_tick(symbol)
        live_price = tick.ask if action == "BUY" else tick.bid if tick else entry_price

        # --- STOP LOSS PADDING & SPREAD DEFENSE ---
        # XM Global Gold spread is ~0.40 - 0.50 points (40-50 pips).
        # A stated SL < 3.0 points from live price will get stopped out by noise.
        # Ensure minimum 3.5 points (35 pips) breathing room.
        min_sl_dist = 3.5 if symbol == "GOLD" else (400.0 if symbol == "BTCUSD" else 0.0035)

        if sl_price is None:
            sl_price = live_price - min_sl_dist if action == "BUY" else live_price + min_sl_dist
        else:
            current_dist = abs(live_price - sl_price)
            if current_dist < min_sl_dist:
                log.info(f"[PERFECT_MGT] 🛡️ Stated SL distance ({current_dist:.2f}) too tight for live spread. Padding to {min_sl_dist:.2f} points.")
                sl_price = round(live_price - min_sl_dist, info.digits) if action == "BUY" else round(live_price + min_sl_dist, info.digits)

        payload = {
            "symbol": symbol,
            "action": action,
            "entry": live_price,
            "final_sl": sl_price,
            "final_tp1": max_tp,
            "comment": "[Perfect Management]",
            "source_channel": "Perfect Management"
        }

        log.info("==================================================")
        log.info(f"💎 [PERFECT MANAGEMENT ORDER] {action} {symbol} @ {live_price} | SL: {sl_price} | Final Target: {max_tp} | Multi-TP Ladder: {dedup_tps}")
        log.info("==================================================")

        success = self.mt5_engine.execute_trade(payload, magic_number=self.magic_number)
        
        status_str = "SUCCESS" if success else "FAILED"
        reason_str = "Executed with AI Runner TSL" if success else "Broker rejected order"
        self._log_audit(action, symbol, live_price, sl_price, max_tp, status_str, reason_str, clean)

        ticket = payload.get("ticket")
        if success and ticket:
            register_trade(
                ticket=ticket,
                symbol=symbol,
                action=action,
                entry=live_price,
                sl=sl_price,
                tps=dedup_tps,
                channel="Perfect Management",
                conviction=0.92
            )
            # Ingest into AI Trade Learning Engine
            learning_engine.record_and_learn_trade(
                channel="Perfect Management",
                account="Account 2",
                symbol=symbol,
                action=action,
                entry=live_price,
                sl=sl_price,
                tps=dedup_tps,
                msg_id=msg_id,
                raw_text=clean,
                ticket=ticket
            )

        return {
            "status": status_str,
            "symbol": symbol,
            "action": action,
            "entry": live_price,
            "sl": sl_price,
            "tps": dedup_tps,
            "ticket": ticket
        }
