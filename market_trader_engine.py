import re
import logging
import csv
from datetime import datetime
from pathlib import Path
import MetaTrader5 as mt5
from real_mt5_execution import MT5ExecutionEngine
from ai_conviction_tsl_manager import register_trade, activate_extension_tsl
from ai_trade_learning_engine import learning_engine

BASE_DIR = Path(__file__).parent
AUDIT_FILE = BASE_DIR / "signals_audit.csv"

log = logging.getLogger(__name__)

# Broker Symbol Mapping for XM Global MT5
BROKER_SYMBOL_MAP = {
    "AUDJPY": "AUDJPY",
    "USDJPY": "USDJPY",
    "GBPCAD": "GBPCAD",
    "GBPJPY": "GBPJPY",
    "EURCAD": "EURCAD",
    "GBPNZD": "GBPNZD",
    "US30": "US30Cash",
    "DJ30": "US30Cash",
    "DOW": "US30Cash",
    "US30CASH": "US30Cash",
    "GOLD": "GOLD",
    "XAUUSD": "GOLD",
    "XAU": "GOLD",
    "BTC": "BTCUSD",
    "BTCUSDT": "BTCUSD",
    "BTCUSD": "BTCUSD",
    "ETH": "ETHUSD",
    "ETHUSDT": "ETHUSD"
}

# Words that MUST NEVER be matched as trading symbols
NON_SYMBOLS = {
    "PIPS", "PIP", "PROFIT", "DONE", "BOOK", "EXIT", "TRADE", "ENTRY",
    "TARGET", "STOP", "LOSS", "COST", "FREE", "LIVE", "VIP", "OPEN",
    "FAST", "NOW", "JOIN", "ALL", "SABHI", "KAR", "LIJIYE", "UPDATE",
    "RUNNING", "SETUP", "STREAM", "DAY", "TODAY", "WEEK", "BEST"
}

# Standard pip distances for Market Trader setups (1 pip = 10 points on 3 & 5 digit pairs)
DEFAULT_SL_TP_PIPS = {
    "AUDJPY": {"sl_pips": 25, "tp_pips": 40},
    "USDJPY": {"sl_pips": 25, "tp_pips": 40},
    "GBPJPY": {"sl_pips": 35, "tp_pips": 60},
    "GBPCAD": {"sl_pips": 30, "tp_pips": 50},
    "EURCAD": {"sl_pips": 30, "tp_pips": 50},
    "GBPNZD": {"sl_pips": 35, "tp_pips": 60},
    "US30Cash": {"sl_pips": 150, "tp_pips": 250},
    "GOLD": {"sl_pips": 45, "tp_pips": 110},  # Refined for intraday protection
    "BTCUSD": {"sl_pips": 400, "tp_pips": 800}
}

class MarketTraderHandler:
    def __init__(self, mt5_engine: MT5ExecutionEngine = None):
        self.mt5_engine = mt5_engine or MT5ExecutionEngine()
        self.magic_number = 888888  # Dedicated Magic for Market Trader
        self.recent_signals = {}    # msg_id -> {"symbol": symbol, "action": action, "ticket": ticket, "time": datetime}

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
                    "Market Trader Crypto Forex",
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

    def resolve_symbol_context(self, clean_text: str, reply_to_msg_id: int = None) -> str:
        """
        Robust symbol resolver:
        1. Checks if reply_to_msg_id maps to an existing trade.
        2. Filters out noise words (PIPS, PROFIT, DONE, etc.).
        3. Falls back to single active MT5 position for Market Trader if unstated.
        """
        # 1. Reply-to message lookup
        if reply_to_msg_id and reply_to_msg_id in self.recent_signals:
            matched_sym = self.recent_signals[reply_to_msg_id].get("symbol")
            if matched_sym:
                log.info(f"[MARKET TRADER] Inherited symbol {matched_sym} from parent msg #{reply_to_msg_id}")
                return matched_sym

        # 2. Extract words and look for real symbol
        words = re.findall(r'\b[A-Za-z0-9_]{3,10}\b', clean_text)
        for w in words:
            u = w.upper()
            if u in NON_SYMBOLS:
                continue
            if u in BROKER_SYMBOL_MAP:
                return BROKER_SYMBOL_MAP[u]
            if len(u) == 6 and u.isalpha():
                return u

        # 3. Fallback: inspect open MT5 positions for this magic number
        if mt5.initialize():
            all_pos = mt5.positions_get()
            mt_pos = [p for p in (all_pos or []) if p.magic == self.magic_number]
            if len(mt_pos) == 1:
                log.info(f"[MARKET TRADER] Auto-resolved symbol {mt_pos[0].symbol} from single active MT5 position #{mt_pos[0].ticket}")
                return mt_pos[0].symbol
            elif len(mt_pos) > 1:
                return None  # Will apply to ALL open positions

        return None

    async def handle_message(self, text: str, has_photo: bool = False, msg_id: int = None, reply_to_msg_id: int = None) -> dict:
        """
        Parses text/caption and handles complete trade lifecycle with robust context inheritance:
        1. Move SL to CTC / Breakeven & Partial Book
        2. Full Take Profit / Trailing Stop Activation
        3. Manual Exit
        4. New Trade Setup (captions, explicit signals, live setups)
        """
        clean_text = text.replace('**', ' ').replace('*', ' ').strip()
        if not clean_text:
            return {"status": "SKIPPED", "reason": "Empty message"}

        # ── 1. Check for Follow-up: Move SL to CTC (Cost to Cost / Breakeven) & Partial Book ──
        if re.search(r'\b(?:sl\s+ctc|sl\s+to\s+ctc|cost\s*to\s*cost|move\s+sl\s+to\s+entry|be\s+kar\s+lijiye)\b', clean_text, re.IGNORECASE):
            target_sym = self.resolve_symbol_context(clean_text, reply_to_msg_id)
            
            # Partial close % (default 40-50%)
            partial_pct = 40
            pct_m = re.search(r'Book\s+([0-9]+)%\s+Profit', clean_text, re.IGNORECASE)
            if pct_m:
                partial_pct = int(pct_m.group(1))

            log.info(f"[MARKET TRADER] ⚡ Intercepted BREAKEVEN + PARTIAL CLOSE for {target_sym or 'ALL'} (Close {partial_pct}%)")
            be_ok = self.mt5_engine.move_sl_to_breakeven(target_sym, self.magic_number)
            pc_ok = self.mt5_engine.close_partial_position(target_sym, partial_pct, self.magic_number)
            
            self._log_audit("MODIFY_BREAKEVEN", target_sym or "ALL", 0, 0, 0, "SUCCESS" if (be_ok or pc_ok) else "NO_OPEN_ORDER", f"SL moved to entry, closed {partial_pct}%", clean_text)
            return {"status": "PROCESSED", "action": "BREAKEVEN_AND_PARTIAL_CLOSE", "symbol": target_sym, "pct": partial_pct}

        # ── 2. Check for Final Book / Full Target Hit ──
        if re.search(r'\bBook\s+([0-9]+)%\s+Profit\b', clean_text, re.IGNORECASE):
            target_sym = self.resolve_symbol_context(clean_text, reply_to_msg_id)
            pct_m = re.search(r'Book\s+([0-9]+)%\s+Profit', clean_text, re.IGNORECASE)
            pct = int(pct_m.group(1)) if pct_m else 80
            
            log.info(f"[MARKET TRADER] Intercepted BOOK {pct}% PROFIT for {target_sym or 'ALL'}")
            if pct >= 80:
                # Switch to 10-pip extension TSL to milk runner
                log.info(f"[MARKET TRADER] ⚡ Switching {target_sym} to 10-pip Extension Trailing Stop!")
                tsl_ok = activate_extension_tsl(target_sym, magic_number=self.magic_number, step_pips=10.0)
                self._log_audit("ACTIVATED_10PIP_TSL", target_sym or "ALL", 0, 0, 0, "SUCCESS" if tsl_ok else "NO_OPEN_ORDER", f"Activated 10-pip jumping TSL on Book {pct}%", clean_text)
                return {"status": "PROCESSED", "action": "ACTIVATED_10PIP_TSL", "symbol": target_sym, "pct": pct}
            else:
                self.mt5_engine.close_partial_position(target_sym, pct, self.magic_number)
                self._log_audit("BOOK_PROFIT", target_sym or "ALL", 0, 0, 0, "SUCCESS", f"Booked {pct}% profit on target hit", clean_text)
                return {"status": "PROCESSED", "action": "BOOK_PROFIT", "symbol": target_sym, "pct": pct}

        # ── 3. Check for Emergency / Manual Exit ──
        if re.search(r'\b(exit\s+kar\s+dijiye|exit\s+now|close\s+all|close\s+now)\b', clean_text, re.IGNORECASE):
            target_sym = self.resolve_symbol_context(clean_text, reply_to_msg_id)
            log.info(f"[MARKET TRADER] 🚨 Intercepted MANUAL EXIT signal for {target_sym or 'ALL positions'}")
            self.mt5_engine.close_position(target_sym, self.magic_number)
            self._log_audit("EXIT", target_sym or "ALL", 0, 0, 0, "SUCCESS", "Manual exit requested by trader", clean_text)
            return {"status": "PROCESSED", "action": "MANUAL_EXIT", "symbol": target_sym}

        # ── 4. Check for New Trade Setup ──
        # Caption matches: 'GBPNZD Long Trade', 'BTCUSDT Short Trade', 'GBPCAD Short Trade'
        trade_cap_match = re.search(r'\b([A-Z0-9_]{3,8})\s+(Long|Short)\s+Trade\b', clean_text, re.IGNORECASE)
        # Explicit signals: 'GOLD BUY 4388', 'BTC SELL 84000'
        explicit_match = re.search(r'(GOLD|XAUUSD|BTC|ETH|[A-Z]{6})\s+(BUY|SELL)\s*[-:]?\s*([0-9]+(?:\.[0-9]+)?)', clean_text, re.IGNORECASE)
        # Live chart setups: 'GOLD LIVE 🚀', 'GOLD LIVE TRADE RUNNING', 'GOLD LIVE MONEY PRINTING'
        live_gold_match = re.search(r'\b(GOLD|XAUUSD)\s+LIVE\b', clean_text, re.IGNORECASE)

        symbol = None
        action = None
        sl_pips = None
        tp_pips = None

        if trade_cap_match:
            raw_sym = trade_cap_match.group(1).upper()
            direction = trade_cap_match.group(2).upper()
            action = "BUY" if direction == "LONG" else "SELL"
            symbol = BROKER_SYMBOL_MAP.get(raw_sym, raw_sym)
            defaults = DEFAULT_SL_TP_PIPS.get(symbol, {"sl_pips": 30, "tp_pips": 50})
            sl_pips = defaults['sl_pips']
            tp_pips = defaults['tp_pips']

        elif explicit_match:
            raw_sym = explicit_match.group(1).upper()
            action = explicit_match.group(2).upper()
            symbol = BROKER_SYMBOL_MAP.get(raw_sym, raw_sym)
            sl_m = re.search(r'SL\s*[-:]?\s*([0-9]+)\s*PIPS', clean_text, re.IGNORECASE)
            sl_pips = int(sl_m.group(1)) if sl_m else 45
            tp_m = re.search(r'(?:TARGET|TP)\s*[-:]?\s*([0-9]+)\s*PIPS', clean_text, re.IGNORECASE)
            tp_pips = int(tp_m.group(1)) if tp_m else 110

        elif live_gold_match:
            symbol = "GOLD"
            action = "SELL" if "SHORT" in clean_text.upper() else "BUY"
            defaults = DEFAULT_SL_TP_PIPS["GOLD"]
            sl_pips = defaults['sl_pips']
            tp_pips = defaults['tp_pips']

        else:
            return {"status": "IGNORED", "reason": "No actionable trade setup or follow-up"}

        # Validate symbol availability on MT5
        if not self.mt5_engine.connected:
            self.mt5_engine.connect()
            
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
        if not info:
            log.error(f"[MARKET TRADER] Symbol {symbol} not available on broker!")
            return {"status": "ERROR", "reason": f"Symbol {symbol} unavailable"}

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return {"status": "ERROR", "reason": f"No tick for {symbol}"}

        live_price = tick.ask if action == "BUY" else tick.bid
        pip_size = 10.0 * info.point
        sl_dist = sl_pips * pip_size
        tp_dist = tp_pips * pip_size

        if action == "BUY":
            sl_price = round(live_price - sl_dist, info.digits)
            tp1_price = round(live_price + (tp_dist * 0.5), info.digits)
            tp2_price = round(live_price + tp_dist, info.digits)
            tp3_price = round(live_price + (tp_dist * 1.5), info.digits)
        else:
            sl_price = round(live_price + sl_dist, info.digits)
            tp1_price = round(live_price - (tp_dist * 0.5), info.digits)
            tp2_price = round(live_price - tp_dist, info.digits)
            tp3_price = round(live_price - (tp_dist * 1.5), info.digits)

        payload = {
            "symbol": symbol,
            "action": action,
            "entry": live_price,
            "final_sl": sl_price,
            "final_tp1": tp1_price,
            "final_tp2": tp2_price,
            "final_tp3": tp3_price,
            "comment": "[Market Trader]",
            "source_channel": "Market Trader"
        }

        log.info("==================================================")
        log.info(f"🚀 [MARKET TRADER ORDER] {action} {symbol} @ {live_price} | SL: {sl_price} ({sl_pips}p) | TP1: {tp1_price} | TP2: {tp2_price} | TP3: {tp3_price}")
        log.info("==================================================")

        success = self.mt5_engine.execute_trade(payload, magic_number=self.magic_number)
        status_str = "SUCCESS" if success else "FAILED"
        ticket = payload.get("ticket")

        if success and ticket:
            # 1. Register trade with TP1, TP2, TP3 for Fixed SL to TP2 & 10-pip Jumping TSL
            register_trade(
                ticket=ticket,
                symbol=symbol,
                action=action,
                entry=live_price,
                sl=sl_price,
                tps=[tp1_price, tp2_price, tp3_price],
                channel="Market Trader",
                conviction=0.90
            )
            # 2. Store in local memory for follow-up reply linking
            if msg_id:
                self.recent_signals[msg_id] = {
                    "symbol": symbol,
                    "action": action,
                    "ticket": ticket,
                    "time": datetime.now()
                }
            # 3. Ingest into AI Trade Learning Engine for SMC reverse-engineering
            learning_engine.record_and_learn_trade(
                channel="Market Trader Crypto Forex",
                account="Account 2",
                symbol=symbol,
                action=action,
                entry=live_price,
                sl=sl_price,
                tps=[tp1_price, tp2_price, tp3_price],
                msg_id=msg_id,
                raw_text=clean_text,
                ticket=ticket
            )

        self._log_audit(action, symbol, live_price, sl_price, tp2_price, status_str, "Executed Market Trader Setup" if success else "Broker rejected", clean_text)

        return {
            "status": status_str,
            "symbol": symbol,
            "action": action,
            "entry": live_price,
            "sl": sl_price,
            "tp": tp2_price,
            "ticket": ticket
        }
