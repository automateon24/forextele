import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

class NewStrategyTemplate:
    def __init__(self, symbol: str, lookback: int = 14):
        self.symbol = symbol
        self.lookback = lookback
        self.strategy_id = "NEW_STRATEGY_TEMPLATE"
        # Require enough data + 2 for closed candle rule
        self.min_bars = self.lookback + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        # STRICT ENFORCEMENT: Only use fully closed bars (iloc[-2] or older)
        latest_closed = df.iloc[-2]
        lookback_data = df.iloc[-self.lookback-2:-2]
        
        # 1. Calculate indicators (e.g. from src.common.indicators)
        # ...
        
        # 2. Check filters (e.g. ADX regime)
        # ...
        
        # 3. Generate Signals
        is_buy = False  # Replace with actual logic
        is_sell = False # Replace with actual logic
        
        if is_buy:
            sl = latest_closed['low'] - 0.0020  # Replace with actual SL logic
            tp = latest_closed['close'] + 0.0040 # Replace with actual TP logic
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
            sl = latest_closed['high'] + 0.0020
            tp = latest_closed['close'] - 0.0040
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
