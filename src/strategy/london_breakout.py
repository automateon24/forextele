import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

class LondonBreakoutStrategy:
    """
    A pure-signal strategy that consumes closed-candle DataFrame
    and emits a SignalMessage if a breakout is detected.
    It has ZERO dependencies on MetaTrader 5 or broker connections.
    """
    def __init__(self, symbol: str, lookback: int = 10):
        self.symbol = symbol
        self.lookback = lookback
        self.strategy_id = "LONDON_BREAKOUT"

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.lookback + 1:
            return None
        
        latest = df.iloc[-1]
        lookback_data = df.iloc[-self.lookback-1:-1]
        
        highest_high = lookback_data['high'].max()
        lowest_low = lookback_data['low'].min()
        
        if latest['close'] > highest_high:
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="BUY",
                strategy_id=self.strategy_id,
                suggested_entry_price=latest['close'],
                suggested_sl_price=lowest_low,
                suggested_tp_price=latest['close'] + (latest['close'] - lowest_low) * 2
            )
        elif latest['close'] < lowest_low:
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="SELL",
                strategy_id=self.strategy_id,
                suggested_entry_price=latest['close'],
                suggested_sl_price=highest_high,
                suggested_tp_price=latest['close'] - (highest_high - latest['close']) * 2
            )
        return None
