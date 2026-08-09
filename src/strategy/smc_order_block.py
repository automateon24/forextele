import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

class SMCOrderBlockStrategy:
    def __init__(self, symbol: str, lookback: int = 50):
        self.symbol = symbol
        self.lookback = lookback
        self.strategy_id = "SMC_ORDER_BLOCK"
        self.min_bars = self.lookback + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        # Strict closed-candle
        latest_closed = df.iloc[-2]
        window = df.iloc[-self.lookback-2:-2]
        
        # A very simplistic SMC Order Block proxy:
        # Find the lowest low in the lookback (liquidity sweep / order block)
        # If the latest close strongly rejects that level, go long.
        lowest_low = window['low'].min()
        highest_high = window['high'].max()
        
        # Bullish rejection
        if latest_closed['low'] <= lowest_low * 1.0005 and latest_closed['close'] > latest_closed['open']:
            sl = lowest_low - 0.0010
            tp = latest_closed['close'] + abs(latest_closed['close'] - sl) * 3
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="BUY",
                strategy_id=self.strategy_id,
                suggested_entry_price=latest_closed['close'],
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )
            
        # Bearish rejection
        if latest_closed['high'] >= highest_high * 0.9995 and latest_closed['close'] < latest_closed['open']:
            sl = highest_high + 0.0010
            tp = latest_closed['close'] - abs(sl - latest_closed['close']) * 3
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
