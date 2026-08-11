import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_rsi, calculate_adx

class MeanReversionStrategy:
    def __init__(self, symbol: str, rsi_period: int = 14, adx_period: int = 14):
        self.symbol = symbol
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.strategy_id = "MEAN_REVERSION"
        # Require enough data for rolling means (e.g. 2x period) + 2 for closed candle
        self.min_bars = max(self.rsi_period, self.adx_period) * 2 + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        # Closed candle rule
        latest_closed = df.iloc[-2]
        
        rsi = calculate_rsi(df['close'], self.rsi_period)
        adx = calculate_adx(df['high'], df['low'], df['close'], self.adx_period)
        
        latest_rsi = rsi.iloc[-2]
        
        if pd.isna(latest_rsi):
            return None
            
        if "GOLD" in self.symbol or "XAU" in self.symbol:
            sl_dist = 2.50
            tp_dist = 5.00
        else:
            sl_dist = 0.0020
            tp_dist = 0.0040
            
        if latest_rsi < 30: # Oversold
            sl = latest_closed['low'] - sl_dist
            tp = latest_closed['close'] + tp_dist
            return SignalMessage(
                header=MessageHeader(source_component="strategy", message_type="Signal"),
                symbol=self.symbol,
                side="BUY",
                strategy_id=self.strategy_id,
                suggested_entry_price=latest_closed['close'],
                suggested_sl_price=sl,
                suggested_tp_price=tp
            )
        elif latest_rsi > 70: # Overbought
            sl = latest_closed['high'] + sl_dist
            tp = latest_closed['close'] - tp_dist
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
