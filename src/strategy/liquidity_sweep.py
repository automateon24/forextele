import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

class LiquiditySweepStrategy:
    def __init__(self, symbol: str, lookback: int = 40):
        self.symbol = symbol
        self.lookback = lookback
        self.strategy_id = "LIQUIDITY_SWEEP"
        self.min_bars = self.lookback + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        lookback_df = df.iloc[-self.lookback-2:-1]  # Exclude forming bar
        latest_closed = df.iloc[-1]
        
        # Identify liquidity pools (Swing High and Swing Low over lookback)
        swing_high = lookback_df['high'].max()
        swing_low = lookback_df['low'].min()
        
        # Dynamic buffer depending on symbol
        if "GOLD" in self.symbol or "XAU" in self.symbol:
            sl_buffer = 1.50
        elif "SILVER" in self.symbol or "XAG" in self.symbol:
            sl_buffer = 0.15
        elif "JPY" in self.symbol:
            sl_buffer = 0.150
        else:
            sl_buffer = 0.0015
        
        # Bullish Sweep (Turtle Soup Long)
        # Price sweeps below the swing low, but closes back above it and bullish
        if latest_closed['low'] < swing_low and latest_closed['close'] > swing_low and latest_closed['close'] > latest_closed['open']:
            sl = latest_closed['low'] - sl_buffer
            risk = latest_closed['close'] - sl
            tp = latest_closed['close'] + risk * 2.0
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="BUY",
                strategy_id=self.strategy_id,
                suggested_entry_price=latest_closed['close'],
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )
            
        # Bearish Sweep (Turtle Soup Short)
        # Price sweeps above the swing high, but closes back below it and bearish
        if latest_closed['high'] > swing_high and latest_closed['close'] < swing_high and latest_closed['close'] < latest_closed['open']:
            sl = latest_closed['high'] + sl_buffer
            risk = sl - latest_closed['close']
            tp = latest_closed['close'] - risk * 2.0
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
