import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_bollinger_bands, calculate_adx

class BollingerMeanReversionStrategy:
    def __init__(self, symbol: str, bb_period: int = 20, bb_std: float = 2.0, adx_period: int = 14):
        self.symbol = symbol
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.adx_period = adx_period
        self.strategy_id = "BOLLINGER_MEAN_REVERSION"
        self.min_bars = max(self.bb_period, self.adx_period) + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        lookback_df = df.iloc[:-1] # Remove forming bar
        
        upper, middle, lower = calculate_bollinger_bands(lookback_df['close'], self.bb_period, self.bb_std)
        adx = calculate_adx(lookback_df['high'], lookback_df['low'], lookback_df['close'], self.adx_period)
        
        current_adx = adx.iloc[-1]
        
        if pd.isna(current_adx) or pd.isna(upper.iloc[-1]):
            return None
            
        # Range filter
        if current_adx >= 20:
            return None
            
        latest_closed = lookback_df.iloc[-1]
        
        # Fade the touch: price touches upper band -> SELL, touches lower band -> BUY
        is_buy = latest_closed['low'] <= lower.iloc[-1] and latest_closed['close'] > lower.iloc[-1]
        is_sell = latest_closed['high'] >= upper.iloc[-1] and latest_closed['close'] < upper.iloc[-1]
        
        if is_buy:
            sl = lower.iloc[-1] - 0.0020
            tp = middle.iloc[-1]
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
            sl = upper.iloc[-1] + 0.0020
            tp = middle.iloc[-1]
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
