import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_rsi, calculate_adx

class RSIReversalStrategy:
    def __init__(self, symbol: str, rsi_period: int = 14, adx_period: int = 14):
        self.symbol = symbol
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.strategy_id = "RSI_REVERSAL"
        self.min_bars = max(self.rsi_period, self.adx_period) * 2 + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        lookback_df = df.iloc[:-1] # Remove forming bar
        
        rsi = calculate_rsi(lookback_df['close'], self.rsi_period)
        adx = calculate_adx(lookback_df['high'], lookback_df['low'], lookback_df['close'], self.adx_period)
        
        current_rsi = rsi.iloc[-1]
        current_adx = adx.iloc[-1]
        
        if pd.isna(current_rsi) or pd.isna(current_adx):
            return None
            
        # Range filter
        if current_adx >= 20:
            return None
            
        latest_closed = lookback_df.iloc[-1]
        
        is_buy = current_rsi < 30
        is_sell = current_rsi > 70
        
        if is_buy:
            sl = latest_closed['low'] - 0.0020
            tp = latest_closed['close'] + 0.0040
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
