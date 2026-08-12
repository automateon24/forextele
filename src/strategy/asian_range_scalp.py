import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

class AsianRangeScalpStrategy:
    def __init__(self, symbol: str, lookback: int = 24, buffer_override: Optional[float] = None, tp_ratio_override: Optional[float] = None): # 24 H1 bars
        self.symbol = symbol
        self.lookback = lookback
        self.buffer_override = buffer_override
        self.tp_ratio_override = tp_ratio_override
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
        
        if self.buffer_override is not None:
            buffer = self.buffer_override
        else:
            if "GOLD" in self.symbol or "XAU" in self.symbol:
                buffer = max(1.00, range_size * 0.05)
            elif "JPY" in self.symbol:
                buffer = max(0.05, range_size * 0.05)
            else:
                buffer = max(0.0005, range_size * 0.05)
            
        tp_ratio = self.tp_ratio_override if self.tp_ratio_override is not None else 1.5
            
        if is_buy:
            sl = range_low - buffer
            risk_dist = abs(latest_closed['close'] - sl)
            tp = latest_closed['close'] + (risk_dist * tp_ratio)
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
            sl = range_high + buffer
            risk_dist = abs(sl - latest_closed['close'])
            tp = latest_closed['close'] - (risk_dist * tp_ratio)
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
