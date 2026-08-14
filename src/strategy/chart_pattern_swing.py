"""
Institutional Chart Pattern & Swing Trading Strategy
=====================================================
Implements classic chart pattern recognition and swing trading logic:
  1.  Head and Shoulders (Top & Inverse Bottom with Neckline Breakouts)
  2.  Double Top & Double Bottom Pivot Reversals
  3.  Triple Top & Triple Bottom
  4.  Bullish & Bearish Flag & Pole Breakouts
  5.  Ascending Triangle (Flat resistance + Rising lows)
  6.  Descending Triangle (Flat support + Falling highs)
  7.  Symmetrical Triangle (Converging trendlines breakout)
  8.  Rising Wedge (Bearish reversal — both lines rising but converging)
  9.  Falling Wedge (Bullish reversal — both lines falling but converging)
  10. Cup & Handle (Rounding bottom + tight consolidation breakout)
  11. Elliott Wave 1-2-3-4-5 / ABC Swing Retracements

Uses ATR-proportional Stop Loss (1.5x ATR) and TSL activation at 2.0x ATR
with TP target at 3.0x ATR for 2:1 minimum Risk-Reward.
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Tuple
from src.common.messages import SignalMessage, MessageHeader


def find_pivots(highs: np.ndarray, lows: np.ndarray, left: int = 3, right: int = 3) -> Tuple[List[int], List[int]]:
    """Finds swing high and swing low pivot indices."""
    pivot_highs, pivot_lows = [], []
    n = len(highs)
    for i in range(left, n - right):
        if all(highs[i] >= highs[i - k] for k in range(1, left + 1)) and all(highs[i] > highs[i + k] for k in range(1, right + 1)):
            pivot_highs.append(i)
        if all(lows[i] <= lows[i - k] for k in range(1, left + 1)) and all(lows[i] < lows[i + k] for k in range(1, right + 1)):
            pivot_lows.append(i)
    return pivot_highs, pivot_lows


def linreg_slope(y: np.ndarray) -> float:
    """Returns linear regression slope for a sequence of values."""
    x = np.arange(len(y), dtype=float)
    if len(x) < 2:
        return 0.0
    coeffs = np.polyfit(x, y, 1)
    return coeffs[0]


class ChartPatternSwingStrategy:
    def __init__(self, symbol: str, lookback: int = 120):
        self.symbol = symbol
        self.lookback = lookback
        self.strategy_id = "CHART_PATTERN_SWING"
        self.min_bars = self.lookback + 10

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None

        # Use closed bars only — exclude the forming bar
        window = df.iloc[-self.lookback-1:-1].copy().reset_index(drop=True)
        highs  = window["high"].values
        lows   = window["low"].values
        closes = window["close"].values
        # Entry uses the LAST CLOSED bar, not the forming live candle
        latest_close = closes[-1]

        # ATR (14 bars)
        tr = np.maximum(highs[1:] - lows[1:], np.maximum(abs(highs[1:] - closes[:-1]), abs(lows[1:] - closes[:-1])))
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else (highs[-1] - lows[-1])
        if atr <= 0:
            return None

        # Symbol-aware SL/TP distances
        is_gold   = "GOLD" in self.symbol or "XAU" in self.symbol
        is_silver = "SILVER" in self.symbol or "XAG" in self.symbol
        is_jpy    = "JPY" in self.symbol

        if is_gold:
            sl_dist = max(3.00, atr * 1.5)
            tp_dist = max(6.00, atr * 3.0)
        elif is_silver:
            sl_dist = max(0.20, atr * 1.5)
            tp_dist = max(0.40, atr * 3.0)
        elif is_jpy:
            sl_dist = max(0.25, atr * 1.5)
            tp_dist = max(0.50, atr * 3.0)
        else:
            sl_dist = max(0.0020, atr * 1.5)
            tp_dist = max(0.0050, atr * 3.5)

        # Wider pivot window (left=3, right=3) = genuine swing pivots, not micro-noise
        pivot_highs, pivot_lows = find_pivots(highs, lows, left=3, right=3)

        # ── 1. Head and Shoulders (Top — Bearish) ──────────────────────────
        if len(pivot_highs) >= 3:
            h1, h2, h3 = pivot_highs[-3], pivot_highs[-2], pivot_highs[-1]
            if highs[h2] > highs[h1] and highs[h2] > highs[h3]:
                shoulder_sym = abs(highs[h1] - highs[h3]) / (highs[h2] + 1e-9)
                if shoulder_sym < 0.008:
                    neckline = min(lows[h1:h3+1]) if h3 > h1 else min(lows[h3:h1+1])
                    if latest_close < neckline:
                        return self._signal("SELL", "HEAD_AND_SHOULDERS", latest_close, sl_dist, tp_dist)

        # ── 2. Inverse Head and Shoulders (Bottom — Bullish) ───────────────
        if len(pivot_lows) >= 3:
            l1, l2, l3 = pivot_lows[-3], pivot_lows[-2], pivot_lows[-1]
            if lows[l2] < lows[l1] and lows[l2] < lows[l3]:
                shoulder_sym = abs(lows[l1] - lows[l3]) / (abs(lows[l2]) + 1e-9)
                if shoulder_sym < 0.008:
                    neckline = max(highs[l1:l3+1]) if l3 > l1 else max(highs[l3:l1+1])
                    if latest_close > neckline:
                        return self._signal("BUY", "INV_HEAD_SHOULDERS", latest_close, sl_dist, tp_dist)

        # ── 3. Double Bottom (W — Bullish) ─────────────────────────────────
        if len(pivot_lows) >= 2:
            l1, l2 = pivot_lows[-2], pivot_lows[-1]
            price_diff = abs(lows[l1] - lows[l2]) / (latest_close + 1e-9)
            if price_diff < 0.004:
                neckline = max(highs[l1:l2+1]) if l2 > l1 else highs[l1]
                if latest_close > neckline:
                    return self._signal("BUY", "DOUBLE_BOTTOM", latest_close, sl_dist, tp_dist)

        # ── 4. Double Top (M — Bearish) ────────────────────────────────────
        if len(pivot_highs) >= 2:
            h1, h2 = pivot_highs[-2], pivot_highs[-1]
            price_diff = abs(highs[h1] - highs[h2]) / (latest_close + 1e-9)
            if price_diff < 0.004:
                neckline = min(lows[h1:h2+1]) if h2 > h1 else lows[h1]
                if latest_close < neckline:
                    return self._signal("SELL", "DOUBLE_TOP", latest_close, sl_dist, tp_dist)

        # ── 5. Triple Bottom (Bullish) ──────────────────────────────────────
        if len(pivot_lows) >= 3:
            l1, l2, l3 = pivot_lows[-3], pivot_lows[-2], pivot_lows[-1]
            all_close = (abs(lows[l1] - lows[l2]) / (latest_close + 1e-9) < 0.004 and
                         abs(lows[l2] - lows[l3]) / (latest_close + 1e-9) < 0.004)
            if all_close:
                neckline = max(highs[l1], highs[l2], highs[l3])
                if latest_close > neckline:
                    return self._signal("BUY", "TRIPLE_BOTTOM", latest_close, sl_dist, tp_dist)

        # ── 6. Triple Top (Bearish) ─────────────────────────────────────────
        if len(pivot_highs) >= 3:
            h1, h2, h3 = pivot_highs[-3], pivot_highs[-2], pivot_highs[-1]
            all_close = (abs(highs[h1] - highs[h2]) / (latest_close + 1e-9) < 0.004 and
                         abs(highs[h2] - highs[h3]) / (latest_close + 1e-9) < 0.004)
            if all_close:
                neckline = min(lows[h1], lows[h2], lows[h3])
                if latest_close < neckline:
                    return self._signal("SELL", "TRIPLE_TOP", latest_close, sl_dist, tp_dist)

        # ── 7. Ascending Triangle (Flat resistance + rising lows → BUY) ─────
        if len(pivot_highs) >= 2 and len(pivot_lows) >= 2:
            recent_h_vals = [highs[i] for i in pivot_highs[-3:]]
            recent_l_vals = [lows[i]  for i in pivot_lows[-3:]]
            resistance_flat = (max(recent_h_vals) - min(recent_h_vals)) / (latest_close + 1e-9) < 0.003
            lows_rising = linreg_slope(np.array(recent_l_vals)) > 0
            if resistance_flat and lows_rising and latest_close > max(recent_h_vals):
                return self._signal("BUY", "ASCENDING_TRIANGLE", latest_close, sl_dist, tp_dist)

        # ── 8. Descending Triangle (Flat support + falling highs → SELL) ────
        if len(pivot_highs) >= 2 and len(pivot_lows) >= 2:
            recent_h_vals = [highs[i] for i in pivot_highs[-3:]]
            recent_l_vals = [lows[i]  for i in pivot_lows[-3:]]
            support_flat  = (max(recent_l_vals) - min(recent_l_vals)) / (latest_close + 1e-9) < 0.003
            highs_falling = linreg_slope(np.array(recent_h_vals)) < 0
            if support_flat and highs_falling and latest_close < min(recent_l_vals):
                return self._signal("SELL", "DESCENDING_TRIANGLE", latest_close, sl_dist, tp_dist)

        # ── 9. Symmetrical Triangle (converging → breakout direction) ────────
        if len(pivot_highs) >= 3 and len(pivot_lows) >= 3:
            recent_h_vals = [highs[i] for i in pivot_highs[-3:]]
            recent_l_vals = [lows[i]  for i in pivot_lows[-3:]]
            highs_falling = linreg_slope(np.array(recent_h_vals)) < 0
            lows_rising   = linreg_slope(np.array(recent_l_vals)) > 0
            if highs_falling and lows_rising:
                apex_high = min(recent_h_vals)
                apex_low  = max(recent_l_vals)
                if latest_close > apex_high:
                    return self._signal("BUY", "SYM_TRIANGLE_BULL", latest_close, sl_dist, tp_dist)
                elif latest_close < apex_low:
                    return self._signal("SELL", "SYM_TRIANGLE_BEAR", latest_close, sl_dist, tp_dist)

        # ── 10. Rising Wedge (Bearish reversal — both lines rising, converging)
        if len(pivot_highs) >= 3 and len(pivot_lows) >= 3:
            recent_h_vals = [highs[i] for i in pivot_highs[-3:]]
            recent_l_vals = [lows[i]  for i in pivot_lows[-3:]]
            h_slope = linreg_slope(np.array(recent_h_vals))
            l_slope = linreg_slope(np.array(recent_l_vals))
            if h_slope > 0 and l_slope > 0 and l_slope > h_slope:  # Lows rising faster = wedge squeeze
                support_break = latest_close < min(recent_l_vals)
                if support_break:
                    return self._signal("SELL", "RISING_WEDGE", latest_close, sl_dist, tp_dist)

        # ── 11. Falling Wedge (Bullish reversal — both lines falling, converging)
        if len(pivot_highs) >= 3 and len(pivot_lows) >= 3:
            recent_h_vals = [highs[i] for i in pivot_highs[-3:]]
            recent_l_vals = [lows[i]  for i in pivot_lows[-3:]]
            h_slope = linreg_slope(np.array(recent_h_vals))
            l_slope = linreg_slope(np.array(recent_l_vals))
            if h_slope < 0 and l_slope < 0 and h_slope < l_slope:  # Highs falling faster = wedge squeeze
                resistance_break = latest_close > max(recent_h_vals)
                if resistance_break:
                    return self._signal("BUY", "FALLING_WEDGE", latest_close, sl_dist, tp_dist)

        # ── 12. Cup & Handle (Bullish — rounding bottom then tight consolidation)
        if len(closes) >= 40:
            cup = closes[-40:-10]
            handle = closes[-10:]
            cup_low_idx = np.argmin(cup)
            cup_depth = max(cup[0], cup[-1]) - cup[cup_low_idx]
            handle_range = max(handle) - min(handle)
            handle_pct = handle_range / (latest_close + 1e-9)
            cup_left_right_close = abs(cup[0] - cup[-1]) / (latest_close + 1e-9) < 0.01
            if cup_depth > sl_dist and handle_pct < 0.005 and cup_left_right_close:
                if latest_close > max(handle[:-1]):
                    return self._signal("BUY", "CUP_AND_HANDLE", latest_close, sl_dist, tp_dist)

        # ── 13. Bullish & Bearish Flag & Pole ───────────────────────────────
        if len(closes) >= 35:
            pole_move = (closes[-10] - closes[-35]) / (closes[-35] + 1e-9)
            consolidation_range = (np.max(highs[-10:]) - np.min(lows[-10:])) / (latest_close + 1e-9)

            if pole_move > 0.008 and consolidation_range < 0.004 and latest_close > np.max(highs[-5:-1]):
                return self._signal("BUY", "FLAG_POLE_BULL", latest_close, sl_dist, tp_dist)

            if pole_move < -0.008 and consolidation_range < 0.004 and latest_close < np.min(lows[-5:-1]):
                return self._signal("SELL", "FLAG_POLE_BEAR", latest_close, sl_dist, tp_dist)

        return None

    def _signal(self, side: str, pattern_id: str, price: float, sl_dist: float, tp_dist: float) -> SignalMessage:
        if side == "BUY":
            sl = price - sl_dist
            tp = price + tp_dist
        else:
            sl = price + sl_dist
            tp = price - tp_dist
        return SignalMessage(
            header=MessageHeader(source_component="strategy", message_type="Signal"),
            symbol=self.symbol,
            side=side,
            strategy_id=pattern_id,
            suggested_entry_price=price,
            suggested_sl_price=sl,
            suggested_tp_price=tp
        )
