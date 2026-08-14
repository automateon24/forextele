import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

class SMCCHoCHStrategy:
    def __init__(self, symbol: str, lookback_major: int = 50, lookback_minor: int = 15):
        self.symbol = symbol
        self.lookback_major = lookback_major
        self.lookback_minor = lookback_minor
        self.strategy_id = "SMC_CHOCH"
        self.min_bars = self.lookback_major + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        # Time-Gate Optimization Filter (CHoCH M15 block NY Open: 12, 13, 14, 15)
        # Determine timeframe
        tf_delta = df.iloc[-1]['time'] - df.iloc[-2]['time']
        if tf_delta == pd.Timedelta(minutes=15) and ("GOLD" in self.symbol or "XAU" in self.symbol):
            current_hour = df.iloc[-1]['time'].hour
            if current_hour in [12, 13, 14, 15]:
                return None
            
        lookback_df = df.iloc[-self.lookback_major-2:-2]  # Exclude forming and latest closed
        latest_closed = df.iloc[-2]
        
        # Major structural points
        major_high = lookback_df['high'].max()
        major_low = lookback_df['low'].min()
        
        # Determine if the major high/low happened recently (within minor lookback)
        recent_df = lookback_df.iloc[-self.lookback_minor:]
        recent_high = recent_df['high'].max()
        recent_low = recent_df['low'].min()
        
        is_recent_major_high = (recent_high == major_high)
        is_recent_major_low = (recent_low == major_low)
        
        sl_buffer = 1.50 if "GOLD" in self.symbol or "XAU" in self.symbol else (0.15 if "SILVER" in self.symbol or "XAG" in self.symbol else 0.0015)
        
        # Bullish CHoCH
        # Recently made a major low, and now breaking above the recent minor high (structural shift)
        if is_recent_major_low and latest_closed['close'] > recent_high and latest_closed['close'] > latest_closed['open']:
            sl = major_low - sl_buffer
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
            
        # Bearish CHoCH
        # Recently made a major high, and now breaking below the recent minor low (structural shift)
        if is_recent_major_high and latest_closed['close'] < recent_low and latest_closed['close'] < latest_closed['open']:
            sl = major_high + sl_buffer
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
