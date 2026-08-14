import pandas as pd
import numpy as np
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader


class EMACrossoverStrategy:
    """
    EMA Crossover Strategy with configurable fast/slow periods.
    Entry: Fast EMA crosses above/below Slow EMA with close confirmation.
    Uses ATR-based SL (1.5x ATR) with TSL activating at +2x ATR profit.
    """
    def __init__(self, symbol: str, fast: int = 9, slow: int = 21):
        self.symbol = symbol
        self.fast = fast
        self.slow = slow
        self.strategy_id = f"EMA_{fast}_{slow}"
        self.min_bars = slow + 5

    def _ema(self, series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None

        closes = df["close"]
        highs  = df["high"].values
        lows   = df["low"].values

        ema_fast = self._ema(closes, self.fast)
        ema_slow = self._ema(closes, self.slow)

        # Need at least 2 bars for crossover detection
        if len(ema_fast) < 2:
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

        latest_close  = closes.iloc[-1]
        prev_fast     = ema_fast.iloc[-2]
        curr_fast     = ema_fast.iloc[-1]
        prev_slow     = ema_slow.iloc[-2]
        curr_slow     = ema_slow.iloc[-1]

        # Bullish Golden Cross: fast crosses above slow
        bullish_cross = prev_fast <= prev_slow and curr_fast > curr_slow
        # Additional filter: price must be above fast EMA
        if bullish_cross and latest_close > curr_fast:
            sl = latest_close - sl_dist
            tp = latest_close + tp_dist
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol, side="BUY", strategy_id=self.strategy_id,
                suggested_entry_price=latest_close,
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )

        # Bearish Death Cross: fast crosses below slow
        bearish_cross = prev_fast >= prev_slow and curr_fast < curr_slow
        # Additional filter: price must be below fast EMA
        if bearish_cross and latest_close < curr_fast:
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
