import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_bollinger_bands, calculate_atr

class BollingerRejectionStrategy:
    def __init__(self, symbol: str, bb_period: int = 20, bb_std: float = 2.0):
        self.symbol = symbol
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.strategy_id = "BOLLINGER_REJECTION"
        self.min_bars = self.bb_period + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        lookback_df = df.iloc[:-1].tail(100) # Remove forming bar and slice for performance
        
        upper, middle, lower = calculate_bollinger_bands(lookback_df['close'], self.bb_period, self.bb_std)

        if pd.isna(upper.iloc[-1]) or pd.isna(lower.iloc[-1]):
            return None

        latest_closed = lookback_df.iloc[-1]
        
        # We want to see a "pin bar" or rejection candle at the bands
        body_size = abs(latest_closed['open'] - latest_closed['close'])
        total_size = latest_closed['high'] - latest_closed['low']
        
        if total_size <= 0:
            return None
            
        upper_wick = latest_closed['high'] - max(latest_closed['open'], latest_closed['close'])
        lower_wick = min(latest_closed['open'], latest_closed['close']) - latest_closed['low']
        
        # Bullish Rejection at Lower Band:
        # Low pierced the lower band, and it closed above the lower band, with a long lower wick.
        is_bullish_rejection = (
            latest_closed['low'] <= lower.iloc[-1] and 
            latest_closed['close'] > lower.iloc[-1] and 
            lower_wick >= body_size * 1.5
        )
        
        # Bearish Rejection at Upper Band:
        # High pierced the upper band, and it closed below the upper band, with a long upper wick.
        is_bearish_rejection = (
            latest_closed['high'] >= upper.iloc[-1] and 
            latest_closed['close'] < upper.iloc[-1] and 
            upper_wick >= body_size * 1.5
        )
        
        # Symbol-aware buffer
        if "GOLD" in self.symbol or "XAU" in self.symbol:
            buffer = 1.00
        elif "JPY" in self.symbol:
            buffer = 0.05
        elif "SILVER" in self.symbol or "XAG" in self.symbol:
            buffer = 0.10
        else:
            buffer = 0.0005
                
        if is_bullish_rejection:
            sl = latest_closed['low'] - buffer
            tp = middle.iloc[-1]
            if tp <= latest_closed['close']:
                tp = latest_closed['close'] + abs(latest_closed['close'] - sl) * 1.5
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="BUY",
                strategy_id=self.strategy_id,
                suggested_entry_price=latest_closed['close'],
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )
        elif is_bearish_rejection:
            sl = latest_closed['high'] + buffer
            tp = middle.iloc[-1]
            if tp >= latest_closed['close']:
                tp = latest_closed['close'] - abs(sl - latest_closed['close']) * 1.5
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
