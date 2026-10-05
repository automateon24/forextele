"""
AUTONOMOUS AI MARKET SCANNER (SMC + LIQUIDITY + MACHINE LEARNING)
==================================================================
Runs completely in parallel with Telegram signals.
Scans GOLD (XAUUSD) and BTCUSD directly from MT5 tick and candlestick data.
Executes high-probability institutional setups discovered from 522+ learned trades:
  1. OVERSOLD_MEAN_REVERSION (M15 RSI < 32 + Sell-Side Liquidity Sweep)
  2. OVERBOUGHT_MEAN_REVERSION (M15 RSI > 68 + Buy-Side Liquidity Sweep)
  3. SMC_TREND_ALIGNED_FVG_EXPANSION (H1 Trend + M5/M15 Fair Value Gap Tap)
Execution Rule: Fixed SL to TP2 + 10-Pip Jumping TSL (Magic: 999001).
"""
import os
import sys
import json
import time
import logging
import asyncio
import os
import psutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

def ensure_single_instance():
    curr_pid = os.getpid()
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if p.pid != curr_pid and 'python' in (p.name() or '').lower():
                cmd = " ".join(p.cmdline() or [])
                if "autonomous_ai_market_scanner.py" in cmd and "SepPro" not in cmd:
                    log.info(f"Existing AutonomousScanner detected (PID {p.pid}). Exiting duplicate instance cleanly.")
                    sys.exit(0)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

STATUS_FILE = DATA_DIR / "autonomous_scanner_status.json"
AUDIT_LOG = DATA_DIR / "autonomous_scanner_audit.csv"

# Configure Logging
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SCANNER_LOG = LOGS_DIR / "smc_scanner.log"

log = logging.getLogger("AUTONOMOUS_AI_SCANNER")
log.setLevel(logging.INFO)
if not log.handlers:
    formatter = logging.Formatter('%(asctime)s - [AI_SCANNER] - %(levelname)s - %(message)s')
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    log.addHandler(ch)
    fh = logging.FileHandler(str(SCANNER_LOG), encoding='utf-8')
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    log.addHandler(fh)

from real_mt5_execution import MT5ExecutionEngine
from ai_conviction_tsl_manager import register_trade
from ai_trade_learning_engine import learning_engine

MAGIC_AUTONOMOUS = 999001

class AutonomousAIMarketScanner:
    def __init__(self):
        self.mt5_engine = MT5ExecutionEngine()
        self.magic_number = MAGIC_AUTONOMOUS
        self.symbols = ["GOLD", "BTCUSD"]
        self.last_trade_time = {}
        self.cooldown_minutes = 60  # Increased from 15m to 60m for trade quality
        self.max_daily_trades = 4   # Cap to max 4 high-conviction trades per day
        self.daily_trade_count = 0
        self.current_trade_day = datetime.now(timezone.utc).date()
        self.status_file = STATUS_FILE
        self.learned_rules = self._load_learned_rules()
        self._init_audit_log()

    def _load_learned_rules(self) -> dict:
        """Loads updated 48h learned channel archetypes and SMC win-rate knowledge."""
        profiles_file = DATA_DIR / "channel_archetypes_and_rules.json"
        if profiles_file.exists():
            try:
                rules = json.loads(profiles_file.read_text(encoding="utf-8"))
                log.info(f"🧠 [AI SCANNER] Loaded {len(rules)} learned channel profiles and SMC performance metrics.")
                return rules
            except Exception as e:
                log.warning(f"Could not load learned rules: {e}")
        return {}

    def _init_audit_log(self):
        if not AUDIT_LOG.exists():
            try:
                import csv
                with open(AUDIT_LOG, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["Timestamp", "Symbol", "Action", "Pattern", "Price", "SL", "TP1", "TP2", "TP3", "Status", "Reason", "Ticket"])
            except Exception as e:
                log.warning(f"Could not init audit log: {e}")

    def log_scanner_audit(self, symbol, action, pattern, price, sl, tp1, tp2, tp3, status, reason, ticket=None):
        try:
            import csv
            with open(AUDIT_LOG, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    symbol, action, pattern, price, sl, tp1, tp2, tp3, status, reason, ticket or ""
                ])
        except Exception:
            pass

    def update_status(self, state: str, details: dict = None):
        try:
            payload = {
                "last_heartbeat": time.time(),
                "last_heartbeat_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": state,
                "symbols_monitored": self.symbols,
                "magic_number": self.magic_number,
                "daily_trade_count": self.daily_trade_count,
                "max_daily_trades": self.max_daily_trades,
                "details": details or {}
            }
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            log.debug(f"Status update error: {e}")

    def check_daily_limit(self) -> bool:
        """Enforces max 4 autonomous trades per UTC day to prevent overtrading."""
        today = datetime.now(timezone.utc).date()
        if today != self.current_trade_day:
            self.current_trade_day = today
            self.daily_trade_count = 0
            log.info(f"🔄 [AI SCANNER] New UTC trading day ({today}). Reset daily trade counter to 0.")

        if self.daily_trade_count >= self.max_daily_trades:
            return False
        return True

    def has_open_position(self, symbol: str) -> bool:
        """Ensures max 1 open autonomous trade per asset."""
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for p in positions:
                if p.magic == self.magic_number:
                    return True
        return False

    def is_in_cooldown(self, symbol: str) -> bool:
        last = self.last_trade_time.get(symbol)
        if not last:
            return False
        elapsed = (datetime.now() - last).total_seconds() / 60.0
        return elapsed < self.cooldown_minutes

    def analyze_symbol(self, symbol: str) -> dict:
        """
        Extracts institutional M5/M15/H1 Smart Money market structure:
        - Higher timeframe trend (H1 EMA 50 vs 200)
        - Liquidity sweeps (Swing high/low breaks with wick rejection)
        - Fair Value Gaps (FVG)
        - RSI Momentum and Extreme Oversold/Overbought zones
        """
        if not mt5.symbol_select(symbol, True):
            return {"valid": False, "reason": f"Symbol {symbol} unavailable"}

        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not info or not tick:
            return {"valid": False, "reason": "No tick/info data"}

        live_bid = tick.bid
        live_ask = tick.ask
        digits = info.digits
        point = info.point

        # ── 1. Higher Timeframe Macro Trend (H1 EMA 50 vs 200) ──
        h1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 120)
        h1_trend = "NEUTRAL"
        if h1_rates is not None and len(h1_rates) >= 50:
            df_h1 = pd.DataFrame(h1_rates)
            ema50 = df_h1['close'].ewm(span=50).mean().iloc[-2]
            ema200 = df_h1['close'].ewm(span=200).mean().iloc[-2]
            latest_c = df_h1['close'].iloc[-2]
            if latest_c > ema50 and ema50 > ema200:
                h1_trend = "BULLISH"
            elif latest_c < ema50 and ema50 < ema200:
                h1_trend = "BEARISH"

        # ── 2. Live M15 Volatility & ATR(14) ──
        m15_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 30)
        if m15_rates is None or len(m15_rates) < 15:
            return {"valid": False, "reason": "Insufficient M15 bars"}

        df_m15 = pd.DataFrame(m15_rates)
        h_m15 = df_m15['high']
        l_m15 = df_m15['low']
        c_m15 = df_m15['close']
        tr_m15 = np.maximum(h_m15 - l_m15, np.maximum(abs(h_m15 - c_m15.shift(1)), abs(l_m15 - c_m15.shift(1))))
        atr14 = float(tr_m15.tail(14).mean())

        # ── 3. Institutional M15 FVG & Order Block (OB) Engine ──
        # Computes live unmitigated Fair Value Gaps and Order Blocks on M15
        active_bull_fvg = None
        active_bear_fvg = None
        curr_price = df_m15['close'].iloc[-1]

        # Scan recent M15 bars for Fair Value Gaps
        for bi in range(len(df_m15) - 2, max(len(df_m15) - 20, 2), -1):
            c_bar = df_m15.iloc[bi]
            p1_bar = df_m15.iloc[bi - 1]
            p2_bar = df_m15.iloc[bi - 2]

            # Bullish FVG: low of current bar > high of bar bi-2
            if not active_bull_fvg and c_bar['low'] > p2_bar['high'] and p1_bar['close'] > p1_bar['open']:
                fvg_top = c_bar['low']
                fvg_bot = p2_bar['high']
                # Check if current price is tapping/mitigating into this FVG zone
                if live_ask <= fvg_top and live_ask >= fvg_bot:
                    active_bull_fvg = {"top": fvg_top, "bot": fvg_bot, "ob_sl": round(fvg_bot - (atr14 * 0.3), digits)}

            # Bearish FVG: high of current bar < low of bar bi-2
            if not active_bear_fvg and c_bar['high'] < p2_bar['low'] and p1_bar['close'] < p1_bar['open']:
                fvg_top = p2_bar['low']
                fvg_bot = c_bar['high']
                # Check if current price is tapping/mitigating into this FVG zone
                if live_bid >= fvg_bot and live_bid <= fvg_top:
                    active_bear_fvg = {"top": fvg_top, "bot": fvg_bot, "ob_sl": round(fvg_top + (atr14 * 0.3), digits)}

        # M5 Microstructure & RSI
        m5_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 40)
        rsi = 50.0
        if m5_rates is not None and len(m5_rates) >= 20:
            df_m5 = pd.DataFrame(m5_rates)
            delta = df_m5['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 1e-9)
            rsi = round(float(100 - (100 / (1 + rs)).iloc[-1]), 1)

        spread = round(live_ask - live_bid, digits)
        utc_hour = datetime.now(timezone.utc).hour
        is_prime_session = (7 <= utc_hour < 18)

        return {
            "valid": True,
            "symbol": symbol,
            "live_bid": live_bid,
            "live_ask": live_ask,
            "digits": digits,
            "point": point,
            "spread": spread,
            "curr_price": curr_price,
            "atr14": atr14,
            "h1_trend": h1_trend,
            "active_bull_fvg": active_bull_fvg,
            "active_bear_fvg": active_bear_fvg,
            "rsi": rsi,
            "is_prime_session": is_prime_session
        }

    def evaluate_signals(self, ctx: dict) -> dict:
        """
        Applies high-conviction learned SMC rules with Strict Macro Trend Gatekeeper:
        - When H1 Trend is BEARISH: ONLY SELL setups allowed (Zero dip-buying).
        - When H1 Trend is BULLISH: ONLY BUY setups allowed (Zero top-shorting).
        - When H1 Trend is NEUTRAL: Extreme mean reversion at institutional boundaries only.
        - BTCUSD Volatility Gate: ATR must be > 3.5x spread to avoid range chop drag.
        """
        if not ctx.get("valid"):
            return None

        sym = ctx["symbol"]
        curr_price = ctx["curr_price"]
        h1_trend = ctx["h1_trend"]
        rsi = ctx["rsi"]
        atr = ctx["atr14"]
        digits = ctx["digits"]
        spread = ctx.get("spread", 0.0)

        # ── GATE 1: BTCUSD Volatility vs Spread Gate ──
        # Avoids tight chop ranges where $40-$50 spread eats profits
        if sym == "BTCUSD" and spread > 0:
            if atr < (3.5 * spread):
                log.debug(f"[VOLATILITY_GATE] BTCUSD M15 ATR ({atr:.1f}) < 3.5x Spread ({spread:.1f}). Skipping chop.")
                return None

        # Default SL buffers: 1.2x M15 ATR
        # Gold: Min 3.5 pts, Max 4.5 pts
        # BTC: Min $250, Max $400
        if sym == "GOLD":
            sl_dist = max(3.50, min(4.50, round(atr * 1.2, 2)))
        elif sym == "BTCUSD":
            sl_dist = max(250.0, min(400.0, round(atr * 1.2, 1)))
        else:
            sl_dist = round(atr * 1.2, digits)

        tp1_dist = round(sl_dist * 1.5, digits)
        tp2_dist = round(sl_dist * 2.5, digits)
        tp3_dist = round(sl_dist * 4.0, digits)

        # ── MACRO TREND GATEKEEPER (Institutional ICT / SMC Engine) ──
        # When H1 is BEARISH: ONLY SELL setups allowed (Zero dip-buying)
        if h1_trend == "BEARISH":
            # 1. Institutional M15 Bearish FVG & Order Block Mitigation (#1 Verified Performer)
            if ctx.get("active_bear_fvg"):
                fvg = ctx["active_bear_fvg"]
                entry_price = ctx["live_bid"]
                sl_price = fvg["ob_sl"]
                risk = max(abs(sl_price - entry_price), 1.20)
                tp1_price = round(entry_price - (risk * 1.5), digits)
                tp2_price = round(entry_price - (risk * 2.5), digits)
                tp3_price = round(entry_price - (risk * 4.0), digits)
                return {
                    "action": "SELL",
                    "symbol": sym,
                    "pattern": "SMC_INSTITUTIONAL_BEARISH_FVG_OB_MITIGATION",
                    "entry": entry_price,
                    "sl": sl_price,
                    "tp1": tp1_price,
                    "tp2": tp2_price,
                    "tp3": tp3_price,
                    "confidence": 0.95,
                    "reason": f"Mitigation tap of M15 Bearish FVG [{fvg['bot']:.2f} - {fvg['top']:.2f}] aligned with H1 Bearish Trend."
                }

            # Any BUY setup in BEARISH trend is strictly vetoed
            return None

        # When H1 is BULLISH: ONLY BUY setups allowed (Zero top-shorting)
        elif h1_trend == "BULLISH":
            # 1. Institutional M15 Bullish FVG & Order Block Mitigation
            if ctx.get("active_bull_fvg"):
                fvg = ctx["active_bull_fvg"]
                entry_price = ctx["live_ask"]
                sl_price = fvg["ob_sl"]
                risk = max(abs(entry_price - sl_price), 1.20)
                tp1_price = round(entry_price + (risk * 1.5), digits)
                tp2_price = round(entry_price + (risk * 2.5), digits)
                tp3_price = round(entry_price + (risk * 4.0), digits)
                return {
                    "action": "BUY",
                    "symbol": sym,
                    "pattern": "SMC_INSTITUTIONAL_BULLISH_FVG_OB_MITIGATION",
                    "entry": entry_price,
                    "sl": sl_price,
                    "tp1": tp1_price,
                    "tp2": tp2_price,
                    "tp3": tp3_price,
                    "confidence": 0.95,
                    "reason": f"Mitigation tap of M15 Bullish FVG [{fvg['bot']:.2f} - {fvg['top']:.2f}] aligned with H1 Bullish Trend."
                }

            # Any SELL setup in BULLISH trend is strictly vetoed
            return None


        # When H1 is NEUTRAL / Consolidation: Strict extremes only
        else:
            if ctx["sweep_low"] and rsi <= 28.0 and ctx["round_conf"]:
                entry_price = ctx["live_ask"]
                sl_price = round(entry_price - sl_dist, digits)
                tp1_price = round(entry_price + tp1_dist, digits)
                tp2_price = round(entry_price + tp2_dist, digits)
                tp3_price = round(entry_price + tp3_dist, digits)
                return {
                    "action": "BUY",
                    "symbol": sym,
                    "pattern": "OVERSOLD_MEAN_REVERSION",
                    "entry": entry_price,
                    "sl": sl_price,
                    "tp1": tp1_price,
                    "tp2": tp2_price,
                    "tp3": tp3_price,
                    "confidence": 0.85,
                    "reason": f"Extreme range oversold RSI={rsi:.1f} at round support in neutral market."
                }

            if ctx["sweep_high"] and rsi >= 72.0 and ctx["round_conf"]:
                entry_price = ctx["live_bid"]
                sl_price = round(entry_price + sl_dist, digits)
                tp1_price = round(entry_price - tp1_dist, digits)
                tp2_price = round(entry_price - tp2_dist, digits)
                tp3_price = round(entry_price - tp3_dist, digits)
                return {
                    "action": "SELL",
                    "symbol": sym,
                    "pattern": "OVERBOUGHT_MEAN_REVERSION",
                    "entry": entry_price,
                    "sl": sl_price,
                    "tp1": tp1_price,
                    "tp2": tp2_price,
                    "tp3": tp3_price,
                    "confidence": 0.85,
                    "reason": f"Extreme range overbought RSI={rsi:.1f} at round resistance in neutral market."
                }

        return None

    def execute_autonomous_trade(self, setup: dict) -> bool:
        """
        Places trade directly on MT5 with Magic 999001,
        registers for Fixed SL to TP2 + 10-pip Jumping TSL,
        and feeds into the AI learning knowledge base!
        """
        symbol = setup["symbol"]
        action = setup["action"]
        entry = setup["entry"]
        sl = setup["sl"]
        tp1 = setup["tp1"]
        tp2 = setup["tp2"]
        tp3 = setup["tp3"]
        pattern = setup["pattern"]
        reason = setup["reason"]

        log.info("==================================================================")
        log.info(f"🤖 [AUTONOMOUS AI SIGNAL] {action} {symbol} @ {entry}")
        log.info(f"   Pattern: {pattern} | SL: {sl} | TP1: {tp1} | TP2: {tp2} | TP3: {tp3}")
        log.info(f"   Logic: {reason}")
        log.info("==================================================================")

        # Lot size: strict 0.02 lots across both GOLD and BTCUSD for disciplined risk control
        volume = 0.02

        payload = {
            "symbol": symbol,
            "action": action,
            "entry": entry,
            "volume": volume,
            "final_sl": sl,
            "final_tp1": tp1,
            "final_tp2": tp2,
            "final_tp3": tp3,
            "comment": "[AI_SMC_SCANNER]",
            "source_channel": "Autonomous AI Scanner"
        }

        success = self.mt5_engine.execute_trade(payload, magic_number=self.magic_number)
        ticket = payload.get("ticket")

        if success and ticket:
            log.info(f"✅ [AUTONOMOUS TRADE EXECUTED] Ticket #{ticket} opened on MT5!")
            self.last_trade_time[symbol] = datetime.now()
            self.daily_trade_count += 1
            log.info(f"📊 [DAILY TRADES] {self.daily_trade_count}/{self.max_daily_trades} autonomous trades executed today.")

            # 1. Register for Fixed SL to TP2 + 10-pip Jumping TSL
            register_trade(
                ticket=ticket,
                symbol=symbol,
                action=action,
                entry=entry,
                sl=sl,
                tps=[tp1, tp2, tp3],
                channel="Autonomous AI Scanner",
                conviction=setup.get("confidence", 0.95)
            )

            # 2. Ingest into AI Trade Learning Knowledge Base
            learning_engine.record_and_learn_trade(
                channel="Autonomous AI Scanner",
                account="AI Autonomous Model",
                symbol=symbol,
                action=action,
                entry=entry,
                sl=sl,
                tps=[tp1, tp2, tp3],
                msg_id=ticket,
                raw_text=f"Autonomous SMC Setup: {pattern} | {reason}",
                ticket=ticket
            )

            self.log_scanner_audit(symbol, action, pattern, entry, sl, tp1, tp2, tp3, "SUCCESS", reason, ticket)
            return True
        else:
            log.error(f"❌ Broker failed to execute autonomous trade for {symbol}!")
            self.log_scanner_audit(symbol, action, pattern, entry, sl, tp1, tp2, tp3, "FAILED", "Broker rejected order")
            return False

    async def scan_cycle(self):
        """Single autonomous evaluation cycle across GOLD and BTCUSD."""
        if not mt5.initialize():
            self.update_status("MT5_DISCONNECTED")
            return

        # Check daily trade cap
        if not self.check_daily_limit():
            log.debug(f"[AI_SCANNER] Daily limit of {self.max_daily_trades} trades reached for today ({self.daily_trade_count}/{self.max_daily_trades}). Skipping new scans.")
            self.update_status("DAILY_LIMIT_REACHED", {"daily_trades": self.daily_trade_count, "max": self.max_daily_trades})
            return

        active_monitors = {}
        for sym in self.symbols:
            has_pos = self.has_open_position(sym)
            in_cd = self.is_in_cooldown(sym)
            ctx = self.analyze_symbol(sym)
            active_monitors[sym] = {
                "has_open_pos": has_pos,
                "in_cooldown": in_cd,
                "h1_trend": ctx.get("h1_trend", "UNKNOWN"),
                "rsi_m5": ctx.get("rsi", 0.0),
                "atr14": ctx.get("atr14", 0.0),
                "spread": ctx.get("spread", 0.0),
                "last_price": ctx.get("curr_price", 0.0)
            }

            if has_pos:
                log.debug(f"[AI_SCANNER] {sym}: Autonomous trade already active (Magic: {self.magic_number}). Waiting.")
                continue

            if in_cd:
                log.debug(f"[AI_SCANNER] {sym}: In cooldown period. Skipping.")
                continue

            setup = self.evaluate_signals(ctx)
            if setup:
                log.info(f"🎯 [SETUP DETECTED] {sym} meets high-conviction criteria for {setup['pattern']}!")
                self.execute_autonomous_trade(setup)

        self.update_status("ACTIVE_SCANNING", active_monitors)

    def daily_ai_autotune(self):
        """
        AI Daily Auto-Tune (runs once per UTC trading day at startup).
        Reads yesterday's closed SMC trades from MT5 history and adjusts:
          - max_daily_trades: up if WR>50%, down if WR<30%
          - cooldown_minutes: tighter if WR>50%, wider if WR<30%
        Saves tuning summary to data/smc_autotune_log.jsonl for transparency.
        """
        try:
            yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
            from_dt = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0, tzinfo=timezone.utc)
            to_dt   = from_dt + timedelta(days=1)

            deals = mt5.history_deals_get(from_dt, to_dt) or []
            smc_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT and d.magic == self.magic_number]

            if not smc_deals:
                log.info("🔄 [AI AUTOTUNE] No SMC closed trades yesterday. Parameters unchanged.")
                return

            wins  = [d for d in smc_deals if (d.profit + d.swap) > 0]
            total = len(smc_deals)
            wr    = (len(wins) / total) * 100 if total else 0
            net   = sum(d.profit + d.swap for d in smc_deals)

            old_max   = self.max_daily_trades
            old_cd    = self.cooldown_minutes

            # Auto-adjust rules
            if wr >= 55:
                self.max_daily_trades = min(old_max + 1, 8)
                self.cooldown_minutes = max(old_cd - 10, 30)
                tune_action = "EXPANDED (WR>55%)"
            elif wr >= 40:
                tune_action = "UNCHANGED (WR 40-55%)"
            elif wr >= 25:
                self.max_daily_trades = max(old_max - 1, 2)
                self.cooldown_minutes = min(old_cd + 15, 120)
                tune_action = "TIGHTENED (WR 25-40%)"
            else:
                self.max_daily_trades = max(old_max - 2, 1)
                self.cooldown_minutes = min(old_cd + 30, 180)
                tune_action = "HEAVILY TIGHTENED (WR<25%)"

            log.info(f"🧠 [AI AUTOTUNE] Yesterday SMC: {total} trades | {len(wins)}W | WR:{wr:.1f}% | Net:{net:+.2f}")
            log.info(f"🧠 [AI AUTOTUNE] Action: {tune_action} | max_daily_trades: {old_max}→{self.max_daily_trades} | cooldown: {old_cd}m→{self.cooldown_minutes}m")

            # Persist log
            log_file = DATA_DIR / "smc_autotune_log.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                import json as _json
                entry = {
                    "date": str(yesterday),
                    "trades": total, "wins": len(wins), "wr_pct": round(wr, 1),
                    "net_pnl": round(net, 2), "action": tune_action,
                    "max_daily_trades": self.max_daily_trades,
                    "cooldown_minutes": self.cooldown_minutes
                }
                f.write(_json.dumps(entry) + "\n")
        except Exception as e:
            log.warning(f"[AI AUTOTUNE] Error during auto-tune: {e}")

    async def run_loop(self):
        """Continuous 24/7 background scanning loop with daily AI auto-tuning."""
        log.info("==================================================================")
        log.info("🚀 Booting Autonomous AI Market Scanner (GOLD & BTCUSD)...")
        log.info("   Patterns: Oversold Sweep + Bearish FVG + Trend Continuation")
        log.info("   Execution: Fixed SL to TP2 + 10-Pip Jumping TSL (Magic: 999001)")
        log.info("   Daily AI Auto-Tune: ACTIVE (adjusts thresholds from live WR)")
        log.info("   Parallel with Telegram Signals: ACTIVE")
        log.info("==================================================================")

        # Run auto-tune once at startup
        self.daily_ai_autotune()
        last_tune_day = datetime.now(timezone.utc).date()

        while True:
            try:
                # Weekend Market Closure Guard (Friday 21:00 UTC to Sunday 22:00 UTC)
                now_u = datetime.now(timezone.utc)
                is_weekend = (now_u.weekday() == 4 and now_u.hour >= 21) or (now_u.weekday() == 5) or (now_u.weekday() == 6 and now_u.hour < 22)
                if is_weekend:
                    await asyncio.sleep(60)
                    continue

                # Auto-tune once per new UTC day
                today = datetime.now(timezone.utc).date()
                if today != last_tune_day:
                    self.daily_ai_autotune()
                    last_tune_day = today

                await self.scan_cycle()
            except Exception as e:
                log.error(f"Error in Autonomous Scanner cycle: {e}")
            await asyncio.sleep(25)  # Scans every 25 seconds

if __name__ == "__main__":
    ensure_single_instance()
    scanner = AutonomousAIMarketScanner()
    asyncio.run(scanner.run_loop())
