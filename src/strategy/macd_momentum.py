import pandas as pd
import numpy as np
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader


class MACDMomentumStrategy:
    """
    MACD Momentum Strategy with configurable fast/slow/signal periods.
    Entry: MACD line crosses Signal line (confirmed by histogram direction).
    Uses ATR-based SL (1.5x ATR) with TSL activating at +2x ATR profit.
    """
    def __init__(self, symbol: str, fast: int = 12, slow: int = 26, signal: int = 9):
        self.symbol = symbol
        self.fast = fast
        self.slow = slow
        self.signal_period = signal
        self.strategy_id = f"MACD_{fast}_{slow}_{signal}"
        self.min_bars = slow + signal + 5

    def _ema(self, series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None

        closes = df["close"]
        highs  = df["high"].values
        lows   = df["low"].values

        # Compute MACD
        ema_fast   = self._ema(closes, self.fast)
        ema_slow   = self._ema(closes, self.slow)
        macd_line  = ema_fast - ema_slow
        signal_line = self._ema(macd_line, self.signal_period)
        histogram  = macd_line - signal_line

        # Need at least last 3 histogram bars for crossover confirmation
        hist = histogram.values
        if len(hist) < 3:
            return None

        # ATR
        tr = np.maximum(highs[1:] - lows[1:],
             np.maximum(abs(highs[1:] - closes.values[:-1]),
                        abs(lows[1:] - closes.values[:-1])))
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else (highs[-1] - lows[-1])
        if atr <= 0:
            return None

        # Symbol-aware SL/TP
        if "GOLD" in self.symbol or "XAU" in self.symbol:
            sl_dist = max(3.00, atr * 1.5)
            tp_dist = max(6.00, atr * 3.0)
        elif "SILVER" in self.symbol or "XAG" in self.symbol:
            sl_dist = max(0.20, atr * 1.5)
            tp_dist = max(0.40, atr * 3.0)
        elif "JPY" in self.symbol:
            sl_dist = max(0.25, atr * 1.5)
            tp_dist = max(0.50, atr * 3.0)
        else:
            sl_dist = max(0.0020, atr * 1.5)
            tp_dist = max(0.0060, atr * 3.5)

        latest_close = closes.iloc[-1]

        # Bullish crossover: histogram flipped from negative to positive (prev bar negative, current positive)
        if hist[-2] < 0 and hist[-1] > 0 and macd_line.iloc[-1] > signal_line.iloc[-1]:
            sl = latest_close - sl_dist
            tp = latest_close + tp_dist
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol, side="BUY", strategy_id=self.strategy_id,
                suggested_entry_price=latest_close,
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )

        # Bearish crossover: histogram flipped from positive to negative
        if hist[-2] > 0 and hist[-1] < 0 and macd_line.iloc[-1] < signal_line.iloc[-1]:
            sl = latest_close + sl_dist
            tp = latest_close - tp_dist
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol, side="SELL", strategy_id=self.strategy_id,
                suggested_entry_price=latest_close,
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )

        return None
