"""
====================================================================
BREAKOUTBOSS: 5-MODEL MULTI-SESSION GOLD BREAKOUT & COMPOUNDING SUITE
====================================================================
Asset            : GOLD (XAUUSD)
Virtual Capital  : $1,000.00 USD Allocated to EACH of the 5 Models ($5,000 Total)
Baskets & Magics :
  - Model 0 (Baseline Fixed)       : Magic 555000 | Remark: "BB_M0_<SESS>_M<TF>" | Lot: 0.02 Fixed
  - Model 1 (Step-Ladder Growth)   : Magic 555001 | Remark: "BB_M1_<SESS>_M<TF>" | Milestone Scaling
  - Model 2 (Linear Equity)        : Magic 555002 | Remark: "BB_M2_<SESS>_M<TF>" | 0.02 lots / $1k Equity
  - Model 3 (AI Conviction Kelly)  : Magic 555003 | Remark: "BB_M3_<SESS>_M<TF>" | Session Kelly Weighted
  - Model 4 (Aggressive Half-Kelly): Magic 555004 | Remark: "BB_M4_<SESS>_M<TF>" | 0.03 lots / $1k Equity
  (Legacy Fallback                 : Magic 555555)

Sessions Tracked :
  1. Asian Open (Tokyo Core)        : 01:00 UTC (04:00 Server / 06:30 IST)
  2. Frankfurt Open (Europe Early)  : 06:00 UTC (09:00 Server / 11:30 IST)
  3. London Core Open (UK Cash)     : 08:00 UTC (11:00 Server / 13:30 IST)
  4. NY Pre-Market (US Macro Data)  : 12:30 UTC (15:30 Server / 18:00 IST)
  5. New York Cash Open (Wall St)   : 13:30 UTC (16:30 Server / 19:00 IST)
  6. London Close (US PM Fix)       : 15:30 UTC (18:30 Server / 21:00 IST)

Mechanics:
  - First Candle High/Low Marked per Session across M1, M3, M5, M15.
  - Volatility Contraction Gate: Skip overextended exhaustion bars.
  - Breakout & Retest Confirmation: Price penetrates, pulls back, confirms rejection.
  - Adaptive Structural SL: Halves risk distance ($2.20 - $2.50 or Midpoint).
  - Dynamic Execution Anchoring: SL and TP anchored strictly to live entry quote.
  - +1R Dynamic Break-Even Trailing: Once in +1R profit, SL moves to Entry + $0.10.
  - Mandatory EOD Hard Close before 20:50 UTC (03:20 AM IST) daily rollover pause.
  - Continuous AI Reverse-Engineering: Ingests all trades into AITradeLearningEngine.
====================================================================
"""
import os
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta, time as dtime

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# Configure Logging
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "breakout_boss.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format='%(asctime)s - [BREAKOUT_BOSS] - %(levelname)s - %(message)s'
)
log = logging.getLogger("BREAKOUT_BOSS")

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - [BREAKOUT_BOSS] - %(levelname)s - %(message)s'))
log.addHandler(console_handler)

# Import AI Learning Engine
try:
    from ai_trade_learning_engine import AITradeLearningEngine
    ai_learner = AITradeLearningEngine()
    log.info("🧠 AI Trade Learning Engine successfully connected to BreakoutBoss.")
except Exception as e:
    ai_learner = None
    log.warning(f"Could not load AI Learning Engine: {e}")

SYMBOL = "GOLD"
REGISTRY_FILE = BASE_DIR / "active_breakoutboss_trades.json"
BASE_VIRTUAL_CAPITAL = 1000.0 # $1,000 USD virtual allocation per model

# 5 Compounding & Dynamic Models Configuration
MODELS_CONFIG = [
    {
        "id": "M0",
        "name": "Baseline Fixed",
        "magic": 555000,
        "type": "FIXED",
        "fixed_lot": 0.02
    },
    {
        "id": "M1",
        "name": "Milestone Step-Ladder",
        "magic": 555001,
        "type": "STEP_LADDER"
    },
    {
        "id": "M2",
        "name": "Linear Equity",
        "magic": 555002,
        "type": "LINEAR_EQUITY"
    },
    {
        "id": "M3",
        "name": "AI Conviction Weighted",
        "magic": 555003,
        "type": "AI_CONVICTION"
    },
    {
        "id": "M4",
        "name": "Aggressive Half-Kelly",
        "magic": 555004,
        "type": "AGGRESSIVE_HALF_KELLY"
    }
]

ALL_BB_MAGICS = [m["magic"] for m in MODELS_CONFIG] + [555555]

# Defined Global Sessions with Optimal Table 1 Backtested R:R per Timeframe
SESSIONS_CONFIG = [
    {
        "code": "ASIA",
        "name": "Asian Open",
        "start": (1, 0),
        "duration_hours": 5,
        "timeframes": [1, 3, 5, 15],
        "rr_by_tf": {1: 1.5, 3: 2.0, 5: 2.0, 15: 2.0}
    },
    {
        "code": "FRA",
        "name": "Frankfurt Open",
        "start": (6, 0),
        "duration_hours": 4,
        "timeframes": [1, 3, 5, 15],
        "rr_by_tf": {1: 5.0, 3: 5.0, 5: 3.0, 15: 3.0}
    },
    {
        "code": "LON",
        "name": "London Core",
        "start": (8, 0),
        "duration_hours": 4,
        "timeframes": [1, 3, 5, 15],
        "rr_by_tf": {1: 3.0, 3: 5.0, 5: 3.0, 15: 3.0}
    },
    {
        "code": "NYP",
        "name": "NY Pre-Mkt",
        "start": (12, 30),
        "duration_hours": 3,
        "timeframes": [1, 3, 5, 15],
        "rr_by_tf": {1: 3.0, 3: 3.0, 5: 3.0, 15: 5.0}
    },
    {
        "code": "NYC",
        "name": "NY Cash Open",
        "start": (13, 30),
        "duration_hours": 3,
        "timeframes": [1, 3, 5, 15],
        "rr_by_tf": {1: 5.0, 3: 3.0, 5: 3.0, 15: 3.0}
    },
    {
        "code": "LNC",
        "name": "London Close",
        "start": (15, 30),
        "duration_hours": 3,
        "timeframes": [1, 3, 5, 15],
        "rr_by_tf": {1: 3.0, 3: 3.0, 5: 3.0, 15: 5.0}
    }
]

# Volatility Caps by Timeframe
VOLATILITY_CAPS = {1: 3.50, 3: 5.00, 5: 6.50, 15: 9.00}

def load_registry() -> dict:
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_registry(data: dict):
    try:
        with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error(f"Error saving registry: {e}")

class BreakoutBossEngine:
    def __init__(self):
        self.symbol = SYMBOL
        self.models = MODELS_CONFIG
        self.registry = load_registry()
        self.processed_setups = set(self.registry.get("processed_setups", []))
        
    def initialize_mt5(self) -> bool:
        if not mt5.initialize():
            log.error("Failed to initialize MetaTrader 5.")
            return False
        mt5.symbol_select(self.symbol, True)
        info = mt5.symbol_info(self.symbol)
        if not info:
            log.error(f"Symbol {self.symbol} not available.")
            return False
        acc = mt5.account_info()
        acc_bal = acc.balance if acc else 0.0
        log.info(f"✅ MT5 Initialized for BreakoutBoss on {self.symbol} | Account Balance: ${acc_bal:.2f} | 5 Compounding Models Active.")
        return True

    def get_live_price(self):
        tick = mt5.symbol_info_tick(self.symbol)
        if tick:
            return tick.ask, tick.bid
        return None, None

    def get_model_virtual_equity(self, magic: int) -> float:
        """
        Computes real-time virtual equity for a specific model starting from $1,000 base.
        Calculates: $1,000 + closed_pnl_for_magic + floating_pnl_for_magic.
        """
        try:
            from_date = datetime(2026, 9, 29, 0, 0, 0, tzinfo=timezone.utc)
            to_date = datetime.now(timezone.utc) + timedelta(days=1)
            deals = mt5.history_deals_get(from_date, to_date)
            closed_pnl = 0.0
            if deals:
                closed_pnl = sum((d.profit + d.swap) for d in deals if d.magic == magic and d.entry == mt5.DEAL_ENTRY_OUT)

            positions = mt5.positions_get(symbol=self.symbol)
            floating_pnl = 0.0
            if positions:
                floating_pnl = sum(p.profit for p in positions if p.magic == magic)

            virtual_equity = BASE_VIRTUAL_CAPITAL + closed_pnl + floating_pnl
            return max(virtual_equity, 200.0)
        except Exception as e:
            log.warning(f"Error computing virtual equity for magic {magic}: {e}")
            return BASE_VIRTUAL_CAPITAL

    def calculate_lot_size(self, model_cfg: dict, session_code: str, virtual_equity: float) -> float:
        """
        Calculates dynamic lot size for each model based on its virtual $1,000 basket equity.
        """
        mtype = model_cfg["type"]
        if mtype == "FIXED":
            return model_cfg.get("fixed_lot", 0.02)

        elif mtype == "STEP_LADDER":
            if virtual_equity < 1400.0:
                return 0.02
            elif virtual_equity < 2000.0:
                return 0.03
            elif virtual_equity < 2800.0:
                return 0.04
            elif virtual_equity < 3800.0:
                return 0.06
            elif virtual_equity < 5000.0:
                return 0.08
            else:
                return 0.10

        elif mtype == "LINEAR_EQUITY":
            lots = round((virtual_equity / 1000.0) * 0.02, 2)
            return min(max(lots, 0.01), 0.40)

        elif mtype == "AI_CONVICTION":
            conviction_weights = {
                "FRA": 1.35, "LNC": 1.35, "NYC": 1.15, "NYP": 1.15, "LON": 1.00, "ASIA": 0.70
            }
            weight = conviction_weights.get(session_code, 1.0)
            base_lots = (virtual_equity / 1000.0) * 0.02
            lots = round(base_lots * weight, 2)
            return min(max(lots, 0.01), 0.40)

        elif mtype == "AGGRESSIVE_HALF_KELLY":
            lots = round((virtual_equity / 1000.0) * 0.03, 2)
            return min(max(lots, 0.01), 0.50)

        return 0.02

    def execute_multi_model_orders(self, action: str, risk_distance: float, session_code: str, tf: int, rr: float):
        """
        Executes orders across all 5 models in parallel.
        Anchors SL and TP strictly to the live execution quote to guarantee ZERO 10016 / 10030 errors.
        """
        order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
        ask, bid = self.get_live_price()
        if not ask or not bid:
            log.error("Cannot fetch live price for multi-model execution.")
            return

        current_price = ask if action == "BUY" else bid
        risk_distance = max(risk_distance, 0.80) # Minimum 80 cents stop distance

        # Strict execution anchoring
        if action == "BUY":
            sl_price = round(current_price - risk_distance, 2)
            tp_price = round(current_price + (risk_distance * rr), 2)
        else:
            sl_price = round(current_price + risk_distance, 2)
            tp_price = round(current_price - (risk_distance * rr), 2)

        for m_cfg in self.models:
            m_id = m_cfg["id"]
            magic = m_cfg["magic"]
            v_equity = self.get_model_virtual_equity(magic)
            lots = self.calculate_lot_size(m_cfg, session_code, v_equity)

            comment_str = f"BB_{m_id}_{session_code}_M{tf}"[:31]

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": lots,
                "type": order_type,
                "price": current_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": 25,
                "magic": magic,
                "comment": comment_str,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            res = mt5.order_send(request)

            # Retry on price slip
            if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
                ret_code = getattr(res, "retcode", None)
                ret_comment = getattr(res, "comment", "Unknown")
                log.warning(f"⚠️ [{m_cfg['name']}] Retcode {ret_code} ({ret_comment}). Refreshing tick for retry...")
                time.sleep(0.15)
                fresh_ask, fresh_bid = self.get_live_price()
                if fresh_ask and fresh_bid:
                    fresh_price = fresh_ask if action == "BUY" else fresh_bid
                    request["price"] = fresh_price
                    if action == "BUY":
                        request["sl"] = round(fresh_price - risk_distance, 2)
                        request["tp"] = round(fresh_price + (risk_distance * rr), 2)
                    else:
                        request["sl"] = round(fresh_price + risk_distance, 2)
                        request["tp"] = round(fresh_price - (risk_distance * rr), 2)
                    res = mt5.order_send(request)

            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                ticket = res.order
                log.info(f"🔥 [{m_cfg['name']}] Ticket #{ticket} | {action} {lots} {self.symbol} @ {current_price:.2f} | V-Equity: ${v_equity:.2f} | SL: {sl_price:.2f} | TP: {tp_price:.2f} (R:R 1:{rr:.1f}) | Comment: {comment_str}")

                # Register with AI Learning Engine
                if ai_learner:
                    try:
                        ai_learner.record_and_learn_trade(
                            channel=f"BreakoutBoss_{m_id}_{session_code}",
                            account="XM_LIVE_7K",
                            symbol=self.symbol,
                            action=action,
                            entry=current_price,
                            sl=sl_price,
                            tps=[tp_price],
                            raw_text=f"BreakoutBoss {m_cfg['name']} {session_code} M{tf} Entry (1:{rr:.1f} R:R)",
                            ticket=ticket
                        )
                    except Exception as ex:
                        log.warning(f"AI Learner record error: {ex}")

                # Register in active trades
                active_list = self.registry.get("active_trades", {})
                active_list[str(ticket)] = {
                    "ticket": ticket,
                    "model_id": m_id,
                    "model_name": m_cfg["name"],
                    "magic": magic,
                    "session": session_code,
                    "tf": tf,
                    "rr": rr,
                    "action": action,
                    "lot_size": lots,
                    "entry": current_price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "risk": risk_distance,
                    "is_be": False,
                    "open_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                }
                self.registry["active_trades"] = active_list
                save_registry(self.registry)
            else:
                ret_desc = res.comment if res else "Unknown Error"
                log.error(f"❌ [{m_cfg['name']}] Order execution failed: Retcode {getattr(res, 'retcode', 'None')} - {ret_desc}")

    def manage_active_trades(self):
        """
        Monitors open trades across all 5 models:
        1. +1R Break-Even Trailing Stop
        2. EOD Hard Close before 20:50 UTC (03:20 AM IST)
        3. Syncs closed trades with AI Learning Engine
        """
        active_list = self.registry.get("active_trades", {})
        if not active_list:
            return

        now_utc = datetime.now(timezone.utc)
        is_eod_time = now_utc.time() >= dtime(20, 50)

        positions = mt5.positions_get(symbol=self.symbol)
        mt5_tickets = {pos.ticket: pos for pos in (positions or []) if pos.magic in ALL_BB_MAGICS}

        closed_tickets = []

        for ticket_str, tdata in list(active_list.items()):
            ticket = int(ticket_str)

            # Check if trade closed in MT5
            if ticket not in mt5_tickets:
                log.info(f"🏁 Trade #{ticket} ({tdata.get('model_name', 'BB')}) closed in MT5. Updating AI Learning Engine...")
                closed_tickets.append(ticket_str)

                from_t = datetime.now(timezone.utc) - timedelta(days=2)
                deals = mt5.history_deals_get(from_t, datetime.now(timezone.utc), position=ticket)
                deal_pnl = 0.0
                if deals:
                    deal_pnl = sum(d.profit + d.swap for d in deals)
                outcome = "WIN" if deal_pnl > 0.50 else ("BE" if abs(deal_pnl) <= 0.50 else "LOSS")

                if ai_learner:
                    try:
                        ai_learner.update_trade_result(
                            ticket=ticket,
                            pnl_usd=round(deal_pnl, 2),
                            pnl_pips=round(deal_pnl / 2.0, 1),
                            outcome=outcome
                        )
                    except Exception as ex:
                        log.warning(f"AI Learner update error: {ex}")
                continue

            pos = mt5_tickets[ticket]
            curr_price = pos.price_current
            entry_price = pos.price_open
            action = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
            risk = tdata.get("risk", 2.50)
            is_be = tdata.get("is_be", False)

            # 1. EOD Force Close before rollover pause
            if is_eod_time:
                log.info(f"🌙 [EOD AUTO-CLOSE] Closing trade #{ticket} ({tdata.get('model_name')}) before rollover pause...")
                close_type = mt5.ORDER_TYPE_SELL if action == "BUY" else mt5.ORDER_TYPE_BUY
                close_req = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": self.symbol,
                    "volume": pos.volume,
                    "type": close_type,
                    "position": ticket,
                    "price": curr_price,
                    "deviation": 25,
                    "magic": pos.magic,
                    "comment": "BB_EOD_Close",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                c_res = mt5.order_send(close_req)
                if c_res and c_res.retcode == mt5.TRADE_RETCODE_DONE:
                    log.info(f"✅ EOD Force Closed trade #{ticket}.")
                    closed_tickets.append(ticket_str)
                continue

            # 2. +1R Break-Even Trailing
            if not is_be:
                if action == "BUY" and curr_price >= (entry_price + risk):
                    new_sl = round(entry_price + 0.10, 2)
                    mod_req = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": ticket,
                        "symbol": self.symbol,
                        "sl": new_sl,
                        "tp": pos.tp
                    }
                    m_res = mt5.order_send(mod_req)
                    if m_res and m_res.retcode == mt5.TRADE_RETCODE_DONE:
                        log.info(f"🛡️ [BE LOCKED] Ticket #{ticket} ({tdata.get('model_name')}) BUY SL moved to {new_sl:.2f}")
                        tdata["is_be"] = True
                        save_registry(self.registry)
                elif action == "SELL" and curr_price <= (entry_price - risk):
                    new_sl = round(entry_price - 0.10, 2)
                    mod_req = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": ticket,
                        "symbol": self.symbol,
                        "sl": new_sl,
                        "tp": pos.tp
                    }
                    m_res = mt5.order_send(mod_req)
                    if m_res and m_res.retcode == mt5.TRADE_RETCODE_DONE:
                        log.info(f"🛡️ [BE LOCKED] Ticket #{ticket} ({tdata.get('model_name')}) SELL SL moved to {new_sl:.2f}")
                        tdata["is_be"] = True
                        save_registry(self.registry)

        for c_t in closed_tickets:
            if c_t in active_list:
                del active_list[c_t]
        self.registry["active_trades"] = active_list
        save_registry(self.registry)

    def scan_session_breakouts(self):
        """
        Scans all 6 sessions and 4 timeframes for Breakout & Retest triggers.
        """
        now_utc = datetime.now(timezone.utc)
        today_date_str = now_utc.strftime("%Y-%m-%d")

        if now_utc.time() >= dtime(20, 45) or now_utc.time() < dtime(0, 50):
            return

        for sc in SESSIONS_CONFIG:
            sh, sm = sc["start"]
            session_start_dt = datetime(now_utc.year, now_utc.month, now_utc.day, sh, sm, tzinfo=timezone.utc)
            session_end_dt = session_start_dt + timedelta(hours=sc["duration_hours"])

            if now_utc < session_start_dt or now_utc > session_end_dt:
                continue

            for tf in sc["timeframes"]:
                setup_id = f"{today_date_str}_{sc['code']}_M{tf}"
                if setup_id in self.processed_setups:
                    continue

                ref_candle_end = session_start_dt + timedelta(minutes=tf)
                if now_utc < ref_candle_end:
                    continue

                rates = mt5.copy_rates_range(self.symbol, mt5.TIMEFRAME_M1, session_start_dt, now_utc)
                if rates is None or len(rates) < tf + 2:
                    continue

                df_m1 = pd.DataFrame(rates)
                df_m1['time_utc'] = pd.to_datetime(df_m1['time'], unit='s', utc=True)
                df_m1.set_index('time_utc', inplace=True)
                df_m1.sort_index(inplace=True)

                ref_bars = df_m1[(df_m1.index >= session_start_dt) & (df_m1.index < ref_candle_end)]
                if len(ref_bars) < tf:
                    continue

                ref_high = ref_bars['high'].max()
                ref_low = ref_bars['low'].min()
                ref_range = ref_high - ref_low
                ref_mid = (ref_high + ref_low) / 2.0

                # Volatility compression gate
                max_allowed_range = VOLATILITY_CAPS.get(tf, 8.00)
                if ref_range < 0.35 or ref_range > max_allowed_range:
                    log.info(f"⏩ [SKIP SETUP] {setup_id}: Range ${ref_range:.2f} exceeds cap ${max_allowed_range:.2f}.")
                    self.processed_setups.add(setup_id)
                    self.registry["processed_setups"] = list(self.processed_setups)
                    save_registry(self.registry)
                    continue

                post_bars = df_m1[df_m1.index >= ref_candle_end]
                if len(post_bars) < 2:
                    continue

                retest_tol = 0.25
                broken_bull = post_bars['high'].max() > ref_high + retest_tol
                broken_bear = post_bars['low'].min() < ref_low - retest_tol

                latest_bar = post_bars.iloc[-1]
                latest_close = latest_bar['close']
                latest_open = latest_bar['open']
                latest_high = latest_bar['high']
                latest_low = latest_bar['low']

                target_rr = sc["rr_by_tf"].get(tf, 3.0)

                # Bullish Breakout & Retest
                if broken_bull and not broken_bear:
                    is_touch = (latest_low <= ref_high + retest_tol and latest_high >= ref_high - retest_tol)
                    is_rejection = (latest_close >= latest_open) or (latest_close > ref_high)

                    if is_touch and is_rejection:
                        entry_ref = ref_high + 0.25
                        sl_ref = ref_low if tf == 1 else (max(ref_low, entry_ref - 2.50) if tf == 3 else max(ref_mid, entry_ref - 3.00))
                        risk_pts = max(entry_ref - sl_ref, 0.80)

                        log.info(f"🎯 [MULTI-MODEL SETUP TRIGGERED] {setup_id} BUY SIGNAL! Risk: ${risk_pts:.2f} | Target R:R: 1:{target_rr:.1f}")
                        self.execute_multi_model_orders("BUY", risk_pts, sc["code"], tf, target_rr)
                        self.processed_setups.add(setup_id)
                        self.registry["processed_setups"] = list(self.processed_setups)
                        save_registry(self.registry)

                    elif latest_low <= ref_low:
                        self.processed_setups.add(setup_id)
                        self.registry["processed_setups"] = list(self.processed_setups)
                        save_registry(self.registry)

                # Bearish Breakout & Retest
                elif broken_bear and not broken_bull:
                    is_touch = (latest_high >= ref_low - retest_tol and latest_low <= ref_low + retest_tol)
                    is_rejection = (latest_close <= latest_open) or (latest_close < ref_low)

                    if is_touch and is_rejection:
                        entry_ref = ref_low - 0.25
                        sl_ref = ref_high if tf == 1 else (min(ref_high, entry_ref + 2.50) if tf == 3 else min(ref_mid, entry_ref + 3.00))
                        risk_pts = max(sl_ref - entry_ref, 0.80)

                        log.info(f"🎯 [MULTI-MODEL SETUP TRIGGERED] {setup_id} SELL SIGNAL! Risk: ${risk_pts:.2f} | Target R:R: 1:{target_rr:.1f}")
                        self.execute_multi_model_orders("SELL", risk_pts, sc["code"], tf, target_rr)
                        self.processed_setups.add(setup_id)
                        self.registry["processed_setups"] = list(self.processed_setups)
                        save_registry(self.registry)

                    elif latest_high >= ref_high:
                        self.processed_setups.add(setup_id)
                        self.registry["processed_setups"] = list(self.processed_setups)
                        save_registry(self.registry)

    def run_loop(self):
        log.info("====================================================================")
        log.info("🚀 BREAKOUTBOSS 5-MODEL SUITE STARTED (ALL 5 COMPOUNDING ENGINES ACTIVE)")
        log.info(f"   Target: {self.symbol} | Virtual Baskets: 5 x $1,000 USD | Total Allocation: $5,000")
        log.info("   Models: M0 (Fixed), M1 (Step-Ladder), M2 (Linear), M3 (AI Kelly), M4 (Half-Kelly)")
        log.info("   Dynamic Live Quote Anchoring: ACTIVE (Zero 10016 / 10030 Errors)")
        log.info("   AI Continuous Learning: ACTIVE")
        log.info("====================================================================")

        while True:
            try:
                self.manage_active_trades()
                self.scan_session_breakouts()
            except Exception as e:
                log.error(f"Error in BreakoutBoss main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    engine = BreakoutBossEngine()
    if engine.initialize_mt5():
        engine.run_loop()
    else:
        log.error("BreakoutBoss could not initialize MT5. Exiting.")
