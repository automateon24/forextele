"""
AI TRADE REVERSE-ENGINEERING & CONTINUOUS LEARNING ENGINE
Analyzes, decodes, and reverse-engineers every trade signal emitted across 40+ Telegram channels.
Captures real-time MT5 Smart Money Concepts (SMC), liquidity sweeps, Order Blocks, FVGs,
and sessions to build a continuous learning knowledge base over 30+ days.
"""
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

LEDGER_FILE = DATA_DIR / "trade_learning_knowledge_base.jsonl"
PROFILES_FILE = DATA_DIR / "channel_archetypes_and_rules.json"

log = logging.getLogger("AI_TRADE_LEARNING")
log.setLevel(logging.INFO)

def get_current_session(dt_utc: datetime) -> str:
    """Returns trading session based on UTC hour."""
    hour = dt_utc.hour
    if 0 <= hour < 7:
        return "ASIAN_SESSION"
    elif 7 <= hour < 12:
        return "LONDON_OPEN"
    elif 12 <= hour < 17:
        return "NY_LONDON_OVERLAP"
    elif 17 <= hour < 21:
        return "NY_AFTERNOON"
    else:
        return "PACIFIC_TRANSITION"

class AITradeLearningEngine:
    def __init__(self):
        self.ledger_file = LEDGER_FILE
        self.profiles_file = PROFILES_FILE

    def analyze_market_context(self, symbol: str, action: str, entry_price: float = None) -> dict:
        """
        Fetches live M5, M15, and H1 data from MT5 to reverse-engineer the SMC context.
        """
        if not mt5.initialize():
            return {"error": "MT5 unavailable"}

        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
        if not info:
            return {"error": f"Symbol {symbol} not found"}

        now_utc = datetime.now(timezone.utc)
        session = get_current_session(now_utc)

        # 1. H1 Trend Analysis (EMA 50 vs EMA 200)
        h1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
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

        # 2. M5 & M15 Structure (Liquidity Sweeps, Order Blocks, FVGs)
        m5_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 60)
        if m5_rates is None or len(m5_rates) < 30:
            return {"session": session, "h1_trend": h1_trend, "hypothesis": "INSUFFICIENT_DATA"}

        df_m5 = pd.DataFrame(m5_rates)
        curr_price = df_m5['close'].iloc[-1] if not entry_price else entry_price

        # Swing High / Low (past 20 bars, excluding last 3)
        swing_high = df_m5['high'].iloc[-25:-3].max()
        swing_low = df_m5['low'].iloc[-25:-3].min()

        # Check Liquidity Sweep
        recent_high = df_m5['high'].iloc[-3:].max()
        recent_low = df_m5['low'].iloc[-3:].min()

        liquidity_sweep_high = recent_high > swing_high and curr_price < swing_high
        liquidity_sweep_low = recent_low < swing_low and curr_price > swing_low

        # Fair Value Gap (FVG)
        df_m5['bull_fvg'] = df_m5['low'] > df_m5['high'].shift(2)
        df_m5['bear_fvg'] = df_m5['high'] < df_m5['low'].shift(2)
        has_bull_fvg = bool(df_m5['bull_fvg'].iloc[-6:-1].any())
        has_bear_fvg = bool(df_m5['bear_fvg'].iloc[-6:-1].any())

        # RSI (14)
        delta = df_m5['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        rsi = round(float(100 - (100 / (1 + rs)).iloc[-1]), 1)

        # Round Institutional Numbers
        round_level_dist = 0.0
        if symbol == "GOLD":
            nearest_round = round(curr_price / 25.0) * 25.0
            round_level_dist = round(abs(curr_price - nearest_round), 2)
        elif symbol == "BTCUSD":
            nearest_round = round(curr_price / 500.0) * 500.0
            round_level_dist = round(abs(curr_price - nearest_round), 1)

        # 3. Reverse Engineer Trading Hypothesis
        hypothesis = "DISCRETIONARY_MOMENTUM"
        confidence = 0.65
        reasons = []

        if action == "SELL":
            if liquidity_sweep_high:
                hypothesis = "SMC_BUY_SIDE_LIQUIDITY_SWEEP_REVERSAL"
                confidence = 0.90
                reasons.append(f"Swept buy-side liquidity above swing high {swing_high:.2f} and rejected.")
            elif has_bear_fvg:
                hypothesis = "SMC_BEARISH_FVG_EXPANSION"
                confidence = 0.85
                reasons.append("Tapped unmitigated M5 Bearish Fair Value Gap.")
            elif h1_trend == "BEARISH":
                hypothesis = "H1_TREND_CONTINUATION_PULLBACK"
                confidence = 0.80
                reasons.append(f"Aligned with macro H1 Bearish Trend (EMA 50 < 200).")
            elif rsi > 68.0:
                hypothesis = "OVERBOUGHT_MEAN_REVERSION"
                confidence = 0.75
                reasons.append(f"RSI overbought ({rsi}), expecting pullback.")
        else: # BUY
            if liquidity_sweep_low:
                hypothesis = "SMC_SELL_SIDE_LIQUIDITY_SWEEP_REVERSAL"
                confidence = 0.90
                reasons.append(f"Swept sell-side liquidity below swing low {swing_low:.2f} and rebounded.")
            elif has_bull_fvg:
                hypothesis = "SMC_BULLISH_FVG_EXPANSION"
                confidence = 0.85
                reasons.append("Tapped unmitigated M5 Bullish Fair Value Gap.")
            elif h1_trend == "BULLISH":
                hypothesis = "H1_TREND_CONTINUATION_PULLBACK"
                confidence = 0.80
                reasons.append(f"Aligned with macro H1 Bullish Trend (EMA 50 > 200).")
            elif rsi < 32.0:
                hypothesis = "OVERSOLD_MEAN_REVERSION"
                confidence = 0.75
                reasons.append(f"RSI oversold ({rsi}), expecting bounce.")

        if round_level_dist > 0 and round_level_dist <= 2.0:
            reasons.append(f"Reacting off institutional psychological level {nearest_round}.")

        logic_summary = " | ".join(reasons) if reasons else "Standard technical price action breakout."

        return {
            "session": str(session),
            "h1_trend": str(h1_trend),
            "swing_high": round(float(swing_high), 4),
            "swing_low": round(float(swing_low), 4),
            "liquidity_sweep": bool(liquidity_sweep_high or liquidity_sweep_low),
            "has_fvg": bool(has_bull_fvg or has_bear_fvg),
            "rsi_14": float(rsi),
            "hypothesis": str(hypothesis),
            "confidence": float(confidence),
            "logic_explanation": str(logic_summary)
        }

    def record_and_learn_trade(
        self,
        channel: str,
        account: str,
        symbol: str,
        action: str,
        entry: float,
        sl: float = None,
        tps: list = None,
        msg_id: int = None,
        raw_text: str = "",
        ticket: int = None
    ) -> dict:
        """
        Reverse engineers and records a new trade signal into the learning knowledge base.
        """
        now = datetime.now(timezone.utc)
        context = self.analyze_market_context(symbol, action, entry)

        record = {
            "timestamp_utc": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "channel": channel,
            "account": account,
            "msg_id": msg_id,
            "ticket": ticket,
            "symbol": symbol,
            "action": action,
            "entry": entry,
            "sl": sl,
            "tps": tps or [],
            "raw_text": (raw_text or "")[:150],
            "market_context": context,
            "status": "OPEN",
            "outcome": None,
            "pnl_usd": 0.0,
            "pnl_pips": 0.0
        }

        # Append to JSONL ledger
        try:
            with open(self.ledger_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            log.info(f"🧠 [AI LEARNING] Reverse-engineered {channel} ({action} {symbol}): Hypothesis='{context.get('hypothesis')}' | Reason: {context.get('logic_explanation')}")
        except Exception as e:
            log.warning(f"Could not append to learning ledger: {e}")

        return record

    def update_trade_result(self, ticket: int, pnl_usd: float, pnl_pips: float, outcome: str):
        """
        Updates trade outcome in the learning ledger when closed.
        """
        if not self.ledger_file.exists():
            return

        try:
            lines = self.ledger_file.read_text(encoding="utf-8").strip().splitlines()
            updated_lines = []
            matched = False
            for line in lines:
                try:
                    rec = json.loads(line)
                    if rec.get("ticket") == ticket:
                        rec["status"] = "CLOSED"
                        rec["outcome"] = outcome
                        rec["pnl_usd"] = pnl_usd
                        rec["pnl_pips"] = pnl_pips
                        rec["closed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                        matched = True
                    updated_lines.append(json.dumps(rec, ensure_ascii=False))
                except Exception:
                    updated_lines.append(line)

            if matched:
                self.ledger_file.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
                self.refresh_channel_profiles()
        except Exception as e:
            log.warning(f"Error updating trade result: {e}")

    def refresh_channel_profiles(self):
        """
        Aggregates learning ledger to build channel SMC DNA profiles and pattern edge.
        """
        if not self.ledger_file.exists():
            return

        from collections import defaultdict
        channel_data = defaultdict(lambda: {
            "total_trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0,
            "hypotheses": defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0}),
            "sessions": defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0}),
            "best_patterns": []
        })

        try:
            for line in self.ledger_file.read_text(encoding="utf-8").strip().splitlines():
                if not line: continue
                rec = json.loads(line)
                ch = rec.get("channel", "Unknown")
                pnl = rec.get("pnl_usd", 0.0)
                outcome = rec.get("outcome")
                ctx = rec.get("market_context", {})
                hyp = ctx.get("hypothesis", "OTHER")
                sess = ctx.get("session", "UNKNOWN")

                c = channel_data[ch]
                c["total_trades"] += 1
                c["total_pnl"] += pnl
                is_win = (outcome and "WIN" in outcome) or pnl > 0
                if is_win:
                    c["wins"] += 1
                elif outcome and "LOSS" in outcome:
                    c["losses"] += 1

                c["hypotheses"][hyp]["count"] += 1
                c["hypotheses"][hyp]["pnl"] += pnl
                if is_win: c["hypotheses"][hyp]["wins"] += 1

                c["sessions"][sess]["count"] += 1
                c["sessions"][sess]["pnl"] += pnl
                if is_win: c["sessions"][sess]["wins"] += 1

            # Format summary
            summary = {
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "channels": {}
            }
            for ch, d in channel_data.items():
                wr = (d["wins"] / d["total_trades"] * 100) if d["total_trades"] > 0 else 0
                best_hyp = sorted(d["hypotheses"].items(), key=lambda x: x[1]["pnl"], reverse=True)
                summary["channels"][ch] = {
                    "total_trades": d["total_trades"],
                    "win_rate": round(wr, 1),
                    "net_pnl": round(d["total_pnl"], 2),
                    "top_smc_pattern": best_hyp[0][0] if best_hyp else "N/A",
                    "pattern_breakdown": {k: {"trades": v["count"], "pnl": round(v["pnl"], 2)} for k, v in d["hypotheses"].items()}
                }

            with open(self.profiles_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning(f"Error refreshing channel profiles: {e}")

# Global instance
learning_engine = AITradeLearningEngine()
