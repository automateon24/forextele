import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

class LondonSessionScalpStrategy:
    def __init__(self, symbol: str, lookback: int = 4):
        self.symbol = symbol
        self.lookback = lookback
        self.strategy_id = "LONDON_SESSION_SCALP"
        self.min_bars = self.lookback + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        latest_closed = df.iloc[-2]
        current_forming = df.iloc[-1]
        
        # London Session: 07:00 to 11:00 UTC
        if not (7 <= latest_closed['time'].hour <= 11):
            return None
            
        lookback_data = df.iloc[-self.lookback-2:-2]
        highest_high = lookback_data['high'].max()
        lowest_low = lookback_data['low'].min()
        
        is_buy = latest_closed['close'] > highest_high
        is_sell = latest_closed['close'] < lowest_low
        
        if is_buy:
            sl = lowest_low
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
            sl = highest_high
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
