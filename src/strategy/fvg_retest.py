import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

# Minimum FVG gap size in dollars (Gold-safe: $1.00 minimum gap)
_MIN_GAP_USD = 1.00
# Stop-loss buffer beyond the gap edge in dollars (Gold-safe: $1.50)
_SL_BUFFER_USD = 1.50


class FVGRetestStrategy:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.strategy_id = "FVG_RETEST"
        self.min_bars = 5  # 3 for FVG formation + 1 for retest + 1 forming

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None

        # Time-Gate Optimization Filter (FVG M15 block: 14, 23, 4)
        current_hour = df.iloc[-1]['time'].hour
        if "GOLD" in self.symbol or "XAU" in self.symbol:
            if current_hour in [14, 23, 4]:
                return None

        lookback_df = df.iloc[:-1]  # Remove forming bar

        c1 = lookback_df.iloc[-4]
        c3 = lookback_df.iloc[-2]
        latest_closed = lookback_df.iloc[-1]

        # Dynamic Gap and Buffer
        min_gap = 1.00 if "GOLD" in self.symbol or "XAU" in self.symbol else (0.10 if "SILVER" in self.symbol or "XAG" in self.symbol else 0.0010)
        sl_buffer = 1.50 if "GOLD" in self.symbol or "XAU" in self.symbol else (0.15 if "SILVER" in self.symbol or "XAG" in self.symbol else 0.0015)

        # Bullish FVG: c1 high is below c3 low → gap exists
        bullish_fvg_gap = c3['low'] - c1['high']
        bullish_fvg = bullish_fvg_gap >= min_gap

        # Bearish FVG: c1 low is above c3 high → gap exists
        bearish_fvg_gap = c1['low'] - c3['high']
        bearish_fvg = bearish_fvg_gap >= min_gap

        # Retest logic: latest closed candle dips into the gap and closes back inside
        is_buy = (
            bullish_fvg
            and (latest_closed['low'] <= c3['low'])
            and (latest_closed['close'] > c1['high'])
        )
        is_sell = (
            bearish_fvg
            and (latest_closed['high'] >= c3['high'])
            and (latest_closed['close'] < c1['low'])
        )

        if is_buy:
            sl = c1['low'] - sl_buffer
            risk = latest_closed['close'] - sl
            tp = latest_closed['close'] + risk * 2.0  # 2:1 R:R
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="BUY",
                strategy_id=self.strategy_id,
                suggested_entry_price=latest_closed['close'],
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )
        elif is_sell:
            sl = c1['high'] + sl_buffer
            risk = sl - latest_closed['close']
            tp = latest_closed['close'] - risk * 2.0  # 2:1 R:R
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="SELL",
                strategy_id=self.strategy_id,
                suggested_entry_price=latest_closed['close'],
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )

        return None
