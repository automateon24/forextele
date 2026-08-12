import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_bollinger_bands, calculate_atr

class BollingerSqueezeBreakoutStrategy:
    def __init__(self, symbol: str, bb_period: int = 20, bb_std: float = 2.0, squeeze_lookback: int = 20, bb_width_percentile: float = 20.0):
        self.symbol = symbol
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.squeeze_lookback = squeeze_lookback
        self.bb_width_percentile = bb_width_percentile
        self.strategy_id = "BOLLINGER_SQUEEZE_BREAKOUT"
        self.min_bars = max(self.bb_period, self.squeeze_lookback) + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        lookback_df = df.iloc[:-1].tail(100) # Remove forming bar and slice for performance
        
        upper, middle, lower = calculate_bollinger_bands(lookback_df['close'], self.bb_period, self.bb_std)
        atr = calculate_atr(lookback_df['high'], lookback_df['low'], lookback_df['close'], 14)

        if pd.isna(upper.iloc[-1]) or pd.isna(lower.iloc[-1]) or pd.isna(atr.iloc[-1]):
            return None

        # Calculate BB Width over the window
        bb_width = upper - lower
        recent_widths = bb_width.iloc[-self.squeeze_lookback:]
        
        # Check if current width is in the lowest percentile (Squeeze condition)
        current_width = bb_width.iloc[-1]
        width_threshold = recent_widths.quantile(self.bb_width_percentile / 100.0)
        
        is_squeeze = current_width <= width_threshold

        latest_closed = lookback_df.iloc[-1]
        prev_closed = lookback_df.iloc[-2]
        
        # We look for a squeeze followed by an expansion/breakout.
        # However, a simpler check is if it WAS in a squeeze recently, and now breaking out.
        # Let's check if there was a squeeze in the last 5 bars.
        was_squeezed = (recent_widths.iloc[-5:] <= width_threshold).any()
        
        # Breakout Condition:
        is_buy_breakout = was_squeezed and prev_closed['close'] <= upper.iloc[-2] and latest_closed['close'] > upper.iloc[-1]
        is_sell_breakout = was_squeezed and prev_closed['close'] >= lower.iloc[-2] and latest_closed['close'] < lower.iloc[-1]
        
        # Symbol-aware buffer
        if "GOLD" in self.symbol or "XAU" in self.symbol:
            buffer = 1.00
        elif "JPY" in self.symbol:
            buffer = 0.05
        elif "SILVER" in self.symbol or "XAG" in self.symbol:
            buffer = 0.10
        else:
            buffer = 0.0005
                
        if is_buy_breakout:
            sl = middle.iloc[-1] - buffer
            tp = latest_closed['close'] + abs(latest_closed['close'] - sl) * 2.0
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="BUY",
                strategy_id=self.strategy_id,
                suggested_entry_price=latest_closed['close'],
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )
        elif is_sell_breakout:
            sl = middle.iloc[-1] + buffer
            tp = latest_closed['close'] - abs(sl - latest_closed['close']) * 2.0
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
