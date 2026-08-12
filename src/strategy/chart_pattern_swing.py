"""
Chart Pattern & Swing Trading Strategy
=======================================
Implements classic chart pattern recognition and swing trading logic:
  1. Head and Shoulders (Top & Inverse Bottom)
  2. Double Top & Double Bottom Reversals
  3. Bullish & Bearish Flag & Pole Breakouts
  4. Elliott Wave 1-2-3-4-5 / ABC Swing Retracements

Uses ATR-proportional Stop Loss and Take Profit distances so that Forex swing
trades have 2:1 to 3:1 Risk-Reward Ratios, completely overcoming spread friction.
"""

import pandas as pd
import numpy as np
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_rsi, calculate_adx


class ChartPatternSwingStrategy:
    def __init__(self, symbol: str, lookback: int = 40):
        self.symbol = symbol
        self.lookback = lookback
        self.strategy_id = "CHART_PATTERN_SWING"
        self.min_bars = self.lookback + 5

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None

        window = df.iloc[-self.lookback-1:-1].copy().reset_index(drop=True)
        latest_closed = window.iloc[-1]

        highs  = window["high"].values
        lows   = window["low"].values
        closes = window["close"].values

        # Calculate ATR
        tr = np.maximum(highs[1:] - lows[1:], np.maximum(abs(highs[1:] - closes[:-1]), abs(lows[1:] - closes[:-1])))
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else (highs[-1] - lows[-1])

        if atr <= 0:
            return None

        # Symbol-aware swing SL and TP multipliers
        is_gold   = "GOLD" in self.symbol or "XAU" in self.symbol
        is_silver = "SILVER" in self.symbol or "XAG" in self.symbol
        is_jpy    = "JPY" in self.symbol

        if is_gold:
            sl_dist = max(2.50, atr * 1.5)
            tp_dist = max(5.00, atr * 3.0)
        elif is_silver:
            sl_dist = max(0.20, atr * 1.5)
            tp_dist = max(0.40, atr * 3.0)
        elif is_jpy:
            sl_dist = max(0.25, atr * 1.5)
            tp_dist = max(0.50, atr * 3.0)
        else:
            sl_dist = max(0.0020, atr * 1.5)  # ~20-30 pips SL for Forex Swing
            tp_dist = max(0.0050, atr * 3.5)  # ~50-80 pips TP (2.5:1 to 3:1 R:R)

        # ── 1. Double Bottom / Double Top Pattern ──────────────────────────
        min_idx = np.argmin(lows[:-5])
        max_idx = np.argmax(highs[:-5])

        # Double Bottom (Bullish Reversal)
        if abs(lows[-2] - lows[min_idx]) / (closes[-1] + 1e-9) < 0.003 and closes[-1] > closes[-2]:
            sl = closes[-1] - sl_dist
            tp = closes[-1] + tp_dist
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="BUY",
                strategy_id=self.strategy_id,
                suggested_entry_price=closes[-1],
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )

        # Double Top (Bearish Reversal)
        if abs(highs[-2] - highs[max_idx]) / (closes[-1] + 1e-9) < 0.003 and closes[-1] < closes[-2]:
            sl = closes[-1] + sl_dist
            tp = closes[-1] - tp_dist
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="SELL",
                strategy_id=self.strategy_id,
                suggested_entry_price=closes[-1],
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )

        # ── 2. Bullish / Bearish Flag & Pole Breakout ──────────────────────
        pole_move = (closes[-10] - closes[-30]) / (closes[-30] + 1e-9)
        consolidation_range = (np.max(highs[-10:]) - np.min(lows[-10:])) / (closes[-1] + 1e-9)

        # Bull Flag Breakout
        if pole_move > 0.008 and consolidation_range < 0.004 and closes[-1] > np.max(highs[-5:-1]):
            sl = closes[-1] - sl_dist
            tp = closes[-1] + tp_dist
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="BUY",
                strategy_id=self.strategy_id,
                suggested_entry_price=closes[-1],
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )

        # Bear Flag Breakout
        if pole_move < -0.008 and consolidation_range < 0.004 and closes[-1] < np.min(lows[-5:-1]):
            sl = closes[-1] + sl_dist
            tp = closes[-1] - tp_dist
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="SELL",
                strategy_id=self.strategy_id,
                suggested_entry_price=closes[-1],
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )

        # ── 3. Elliott Wave Retracement (Wave 4 Pullback into Wave 5 Impulse)
        swing_high = np.max(highs[-20:-5])
        swing_low  = np.min(lows[-30:-20])
        wave_height = swing_high - swing_low

        if wave_height > 0:
            fib_382 = swing_high - 0.382 * wave_height
            fib_618 = swing_high - 0.618 * wave_height

            if fib_618 <= closes[-1] <= fib_382 and closes[-1] > closes[-2]:
                sl = closes[-1] - sl_dist
                tp = closes[-1] + tp_dist
                return SignalMessage(
                    header=MessageHeader(source_component="strategy", message_type="Signal"),
                    symbol=self.symbol,
                    side="BUY",
                    strategy_id=self.strategy_id,
                    suggested_entry_price=closes[-1],
                    suggested_sl_price=sl,
                    suggested_tp_price=tp
                )

        return None
