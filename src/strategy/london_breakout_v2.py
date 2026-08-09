import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_atr

class LondonBreakoutV2Strategy:
    def __init__(self, symbol: str, lookback: int = 4):
        self.symbol = symbol
        self.lookback = lookback
        self.strategy_id = "LONDON_BREAKOUT_V2"
        self.min_bars = max(self.lookback + 2, 16) # Need 14 for ATR minimum

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        latest_closed = df.iloc[-2]
        
        # London Open typically 07:00 to 10:00 UTC
        if not (7 <= latest_closed['time'].hour <= 10):
            return None
            
        lookback_data = df.iloc[-self.lookback-2:-2]
        london_high = lookback_data['high'].max()
        london_low = lookback_data['low'].min()
        
        range_size = london_high - london_low
        atr = calculate_atr(df['high'], df['low'], df['close'], 14).iloc[-2]
        
        if pd.isna(atr):
            return None
            
        # Minimum range filter: range must be at least 0.5 ATR
        if range_size < (0.5 * atr):
            return None
            
        is_buy = latest_closed['close'] > london_high
        is_sell = latest_closed['close'] < london_low
        
        if is_buy:
            sl = latest_closed['close'] - (1.5 * atr) # ATR based SL
            tp = latest_closed['close'] + (2.0 * atr)
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
            sl = latest_closed['close'] + (1.5 * atr)
            tp = latest_closed['close'] - (2.0 * atr)
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
