import pandas as pd
import numpy as np
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_adx


class ForexAsianSweepRegimeStrategy:
    """
    Institutional Forex Strategy: Asian Range Liquidity Sweep with ADX Regime Switching.
    
    1. Asian Range Calculation: Identifies High & Low between 22:00 UTC and 07:00 UTC.
    2. Execution Window: London Open (07:00 UTC - 11:00 UTC).
    3. ADX Regime Switch:
       - ADX < 20 (Ranging): Fade the sweep (Liquidity Trap / Mean Reversion).
       - ADX > 25 (Trending): Trade the breakout (Institutional Expansion).
    4. Tight Forex SL: 15-20 pips depending on pair.
    """

    def __init__(
        self,
        symbol: str,
        adx_period: int = 14,
        sl_pips: Optional[float] = None,
        tp_ratio_range: float = 1.5,
        tp_ratio_trend: float = 2.0
    ):
        self.symbol = symbol
        self.adx_period = adx_period
        self.strategy_id = "FOREX_ASIAN_SWEEP_REGIME"
        self.min_bars = 50

        # Pair-specific pip scaling
        is_gbp = "GBP" in symbol
        is_jpy = "JPY" in symbol

        if sl_pips is not None:
            self.sl_dist = sl_pips
        elif is_gbp:
            self.sl_dist = 0.0020  # 20 pips
        elif is_jpy:
            self.sl_dist = 0.20    # 20 pips
        else:
            self.sl_dist = 0.0015  # 15 pips for EURUSD

        self.tp_ratio_range = tp_ratio_range
        self.tp_ratio_trend = tp_ratio_trend

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None

        # Work on closed bars (exclude currently forming bar)
        closed_df = df.iloc[:-1].copy()
        current_bar = closed_df.iloc[-1]
        current_time = current_bar["time"]
        current_hour = current_time.hour

        # Execution Window: London Open (07:00 to 11:00 UTC)
        if not (7 <= current_hour <= 11):
            return None

        # Extract Asian Session bars (from 22:00 UTC previous day up to 07:00 UTC current day)
        # Look back up to 48 bars (12 hours on M15, or 24 hours on M15)
        last_24h = closed_df[closed_df["time"] >= (current_time - pd.Timedelta(hours=24))]
        asian_bars = last_24h[last_24h["time"].dt.hour.isin([22, 23, 0, 1, 2, 3, 4, 5, 6])]

        if len(asian_bars) < 8:
            return None

        asian_high = asian_bars["high"].max()
        asian_low = asian_bars["low"].min()
        asian_range = asian_high - asian_low

        if asian_range <= 0:
            return None

        # Check for sweeps on current closed bar
        swept_above = current_bar["high"] > asian_high
        swept_below = current_bar["low"] < asian_low

        if not swept_above and not swept_below:
            return None

        # Calculate ADX(14) for regime classification
        adx_series = calculate_adx(closed_df["high"], closed_df["low"], closed_df["close"], period=self.adx_period)
        if adx_series.empty or pd.isna(adx_series.iloc[-1]):
            return None

        current_adx = adx_series.iloc[-1]
        price = current_bar["close"]

        # ── REGIME 1: RANGING MARKET (ADX < 20) → FADE THE SWEEP ──────────────
        if current_adx < 20:
            if swept_above:
                # Bearish Fakeout -> SELL
                sl = price + self.sl_dist
                tp = price - (self.sl_dist * self.tp_ratio_range)
                return SignalMessage(
                    header=MessageHeader(source_component="strategy", message_type="Signal"),
                    symbol=self.symbol, side="SELL", strategy_id=self.strategy_id,
                    suggested_entry_price=price, suggested_sl_price=sl, suggested_tp_price=tp
                )
            elif swept_below:
                # Bullish Fakeout -> BUY
                sl = price - self.sl_dist
                tp = price + (self.sl_dist * self.tp_ratio_range)
                return SignalMessage(
                    header=MessageHeader(source_component="strategy", message_type="Signal"),
                    symbol=self.symbol, side="BUY", strategy_id=self.strategy_id,
                    suggested_entry_price=price, suggested_sl_price=sl, suggested_tp_price=tp
                )

        # ── REGIME 2: TRENDING MARKET (ADX > 25) → TRADE THE BREAKOUT ────────
        elif current_adx > 25:
            if swept_above and price > asian_high:
                # Bullish Breakout Continuation -> BUY
                sl = price - self.sl_dist
                tp = price + (self.sl_dist * self.tp_ratio_trend)
                return SignalMessage(
                    header=MessageHeader(source_component="strategy", message_type="Signal"),
                    symbol=self.symbol, side="BUY", strategy_id=self.strategy_id,
                    suggested_entry_price=price, suggested_sl_price=sl, suggested_tp_price=tp
                )
            elif swept_below and price < asian_low:
                # Bearish Breakdown Continuation -> SELL
                sl = price + self.sl_dist
                tp = price - (self.sl_dist * self.tp_ratio_trend)
                return SignalMessage(
                    header=MessageHeader(source_component="strategy", message_type="Signal"),
                    symbol=self.symbol, side="SELL", strategy_id=self.strategy_id,
                    suggested_entry_price=price, suggested_sl_price=sl, suggested_tp_price=tp
                )

        return None
