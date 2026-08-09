import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

class ORBOpeningRangeBreakoutStrategy:
    def __init__(self, symbol: str, lookback: int = 4, max_range_pips: float = 0.0030):
        self.symbol = symbol
        self.lookback = lookback # Number of bars to define the range (e.g. 4 H1 bars)
        self.max_range = max_range_pips
        self.strategy_id = "ORB_OPENING_RANGE_BREAKOUT"
        self.min_bars = self.lookback + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        latest_closed = df.iloc[-2]
        
        # Breakout evaluated at hour 12 UTC (after 08:00 to 12:00 window)
        if latest_closed['time'].hour != 12:
            return None
            
        lookback_data = df.iloc[-self.lookback-2:-2]
        orb_high = lookback_data['high'].max()
        orb_low = lookback_data['low'].min()
        range_size = orb_high - orb_low
        
        # Filter out if range is too large (choppy/volatile open)
        if range_size > self.max_range:
            return None
            
        is_buy = latest_closed['close'] > orb_high
        is_sell = latest_closed['close'] < orb_low
        
        if is_buy:
            sl = orb_low
            tp = latest_closed['close'] + (latest_closed['close'] - sl) * 1.5
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
            sl = orb_high
            tp = latest_closed['close'] - (sl - latest_closed['close']) * 1.5
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
