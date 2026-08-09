import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_rsi, calculate_adx

class TrendMomentumStrategy:
    def __init__(self, symbol: str, rsi_period: int = 14, adx_period: int = 14):
        self.symbol = symbol
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.strategy_id = "TREND_MOMENTUM"
        self.min_bars = max(self.rsi_period, self.adx_period) * 2 + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        latest_closed = df.iloc[-2]
        
        rsi = calculate_rsi(df['close'], self.rsi_period)
        adx = calculate_adx(df['high'], df['low'], df['close'], self.adx_period)
        
        latest_rsi = rsi.iloc[-2]
        latest_adx = adx.iloc[-2]
        
        # Trend strategy requires strong trend (ADX > 25)
        if pd.isna(latest_adx) or latest_adx <= 25:
            return None
            
        # Buy on strong upward momentum
        if latest_rsi > 60:
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
        # Sell on strong downward momentum
        elif latest_rsi < 40:
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
