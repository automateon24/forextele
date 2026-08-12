"""
Institutional Chart Pattern & Swing Trading Strategy
=====================================================
Implements classic chart pattern recognition and swing trading logic:
  1. Head and Shoulders (Top & Inverse Bottom with Neckline Breakouts)
  2. Double Top & Double Bottom Pivot Reversals
  3. Bullish & Bearish Flag & Pole Breakouts
  4. Elliott Wave 1-2-3-4-5 / ABC Swing Retracements

Uses ATR-proportional Stop Loss (1.5x ATR) and Take Profit (3.0x to 3.5x ATR)
so that swing trades have 2.0:1 to 2.5:1 Risk-Reward Ratios.
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Tuple
from src.common.messages import SignalMessage, MessageHeader


def find_pivots(highs: np.ndarray, lows: np.ndarray, left: int = 3, right: int = 3) -> Tuple[List[int], List[int]]:
    """
    Finds swing high and swing low pivot indices.
    """
    pivot_highs, pivot_lows = [], []
    n = len(highs)
    for i in range(left, n - right):
        if all(highs[i] >= highs[i - k] for k in range(1, left + 1)) and all(highs[i] > highs[i + k] for k in range(1, right + 1)):
            pivot_highs.append(i)
        if all(lows[i] <= lows[i - k] for k in range(1, left + 1)) and all(lows[i] < lows[i + k] for k in range(1, right + 1)):
            pivot_lows.append(i)
    return pivot_highs, pivot_lows


class ChartPatternSwingStrategy:
    def __init__(self, symbol: str, lookback: int = 50):
        self.symbol = symbol
        self.lookback = lookback
        self.strategy_id = "CHART_PATTERN_SWING"
        self.min_bars = self.lookback + 5

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None

        window = df.iloc[-self.lookback-1:-1].copy().reset_index(drop=True)
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
            tp_dist = max(0.0050, atr * 3.5)  # ~50-80 pips TP (2.5:1 R:R)

        pivot_highs, pivot_lows = find_pivots(highs, lows, left=2, right=2)

        # ── 1. Head and Shoulders (Top & Inverse Bottom) ───────────────────
        if len(pivot_highs) >= 3:
            h1, h2, h3 = pivot_highs[-3], pivot_highs[-2], pivot_highs[-1]
            # Standard Head and Shoulders (Bearish): H2 is highest, H1 and H3 are left/right shoulders
            if highs[h2] > highs[h1] and highs[h2] > highs[h3] and abs(highs[h1] - highs[h3]) / highs[h2] < 0.005:
                neckline = min(lows[h1:h3])
                if closes[-1] < neckline:
                    sl = closes[-1] + sl_dist
                    tp = closes[-1] - tp_dist
                    return SignalMessage(
                        header=MessageHeader(source_component="strategy", message_type="Signal"),
                        symbol=self.symbol, side="SELL", strategy_id=self.strategy_id,
                        suggested_entry_price=closes[-1], suggested_sl_price=sl, suggested_tp_price=tp
                    )

        if len(pivot_lows) >= 3:
            l1, l2, l3 = pivot_lows[-3], pivot_lows[-2], pivot_lows[-1]
            # Inverse Head and Shoulders (Bullish): L2 is lowest, L1 and L3 are left/right shoulders
            if lows[l2] < lows[l1] and lows[l2] < lows[l3] and abs(lows[l1] - lows[l3]) / (abs(lows[l2]) + 1e-9) < 0.005:
                neckline = max(highs[l1:l3])
                if closes[-1] > neckline:
                    sl = closes[-1] - sl_dist
                    tp = closes[-1] + tp_dist
                    return SignalMessage(
                        header=MessageHeader(source_component="strategy", message_type="Signal"),
                        symbol=self.symbol, side="BUY", strategy_id=self.strategy_id,
                        suggested_entry_price=closes[-1], suggested_sl_price=sl, suggested_tp_price=tp
                    )

        # ── 2. Double Bottom & Double Top Reversals ────────────────────────
        if len(pivot_lows) >= 2:
            l1, l2 = pivot_lows[-2], pivot_lows[-1]
            if abs(lows[l1] - lows[l2]) / (closes[-1] + 1e-9) < 0.003 and closes[-1] > max(highs[l1:l2]):
                sl = closes[-1] - sl_dist
                tp = closes[-1] + tp_dist
                return SignalMessage(
                    header=MessageHeader(source_component="strategy", message_type="Signal"),
                    symbol=self.symbol, side="BUY", strategy_id=self.strategy_id,
                    suggested_entry_price=closes[-1], suggested_sl_price=sl, suggested_tp_price=tp
                )

        if len(pivot_highs) >= 2:
            h1, h2 = pivot_highs[-2], pivot_highs[-1]
            if abs(highs[h1] - highs[h2]) / (closes[-1] + 1e-9) < 0.003 and closes[-1] < min(lows[h1:h2]):
                sl = closes[-1] + sl_dist
                tp = closes[-1] - tp_dist
                return SignalMessage(
                    header=MessageHeader(source_component="strategy", message_type="Signal"),
                    symbol=self.symbol, side="SELL", strategy_id=self.strategy_id,
                    suggested_entry_price=closes[-1], suggested_sl_price=sl, suggested_tp_price=tp
                )

        # ── 3. Bullish & Bearish Flag & Pole Breakouts ─────────────────────
        pole_move = (closes[-10] - closes[-35]) / (closes[-35] + 1e-9)
        consolidation_range = (np.max(highs[-10:]) - np.min(lows[-10:])) / (closes[-1] + 1e-9)

        if pole_move > 0.008 and consolidation_range < 0.004 and closes[-1] > np.max(highs[-5:-1]):
            sl = closes[-1] - sl_dist
            tp = closes[-1] + tp_dist
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol, side="BUY", strategy_id=self.strategy_id,
                suggested_entry_price=closes[-1], suggested_sl_price=sl, suggested_tp_price=tp
            )

        if pole_move < -0.008 and consolidation_range < 0.004 and closes[-1] < np.min(lows[-5:-1]):
            sl = closes[-1] + sl_dist
            tp = closes[-1] - tp_dist
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol, side="SELL", strategy_id=self.strategy_id,
                suggested_entry_price=closes[-1], suggested_sl_price=sl, suggested_tp_price=tp
            )

        # ── 4. Elliott Wave Retracement (Wave 4 Pullback into Wave 5 Impulse)
        if len(pivot_highs) >= 1 and len(pivot_lows) >= 1:
            last_high_idx = pivot_highs[-1]
            last_low_idx  = pivot_lows[-1]

            if last_high_idx > last_low_idx:
                wave_height = highs[last_high_idx] - lows[last_low_idx]
                if wave_height > 0:
                    fib_382 = highs[last_high_idx] - 0.382 * wave_height
                    fib_618 = highs[last_high_idx] - 0.618 * wave_height
                    if fib_618 <= closes[-1] <= fib_382 and closes[-1] > closes[-2]:
                        sl = closes[-1] - sl_dist
                        tp = closes[-1] + tp_dist
                        return SignalMessage(
                            header=MessageHeader(source_component="strategy", message_type="Signal"),
                            symbol=self.symbol, side="BUY", strategy_id=self.strategy_id,
                            suggested_entry_price=closes[-1], suggested_sl_price=sl, suggested_tp_price=tp
                        )

        return None
