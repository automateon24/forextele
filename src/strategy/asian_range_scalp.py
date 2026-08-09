import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

class AsianRangeScalpStrategy:
    def __init__(self, symbol: str, lookback: int = 24): # 24 H1 bars
        self.symbol = symbol
        self.lookback = lookback
        self.strategy_id = "ASIAN_RANGE_SCALP"
        self.min_bars = self.lookback + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        latest_closed = df.iloc[-2]
        # Asian session is typically 23:00 to 08:00 UTC (using simple hour check for demo)
        if not (0 <= latest_closed['time'].hour <= 8 or latest_closed['time'].hour == 23):
            return None
            
        lookback_data = df.iloc[-self.lookback-2:-2]
        range_high = lookback_data['high'].max()
        range_low = lookback_data['low'].min()
        
        # Simple fade: if close is near the high, sell. If near the low, buy.
        range_size = range_high - range_low
        if range_size == 0:
            return None
            
        is_buy = latest_closed['close'] <= (range_low + range_size * 0.1) # Bottom 10%
        is_sell = latest_closed['close'] >= (range_high - range_size * 0.1) # Top 10%
        
        if is_buy:
            sl = range_low - 0.0020
            tp = range_high
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
            sl = range_high + 0.0020
            tp = range_low
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
