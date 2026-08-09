import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_vwap, calculate_adx

class VWAPMeanReversionStrategy:
    def __init__(self, symbol: str, adx_period: int = 14):
        self.symbol = symbol
        self.adx_period = adx_period
        self.strategy_id = "VWAP_MEAN_REVERSION"
        self.min_bars = self.adx_period + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        lookback_df = df.iloc[:-1] # Remove forming bar
        
        # VWAP usually resets daily. Let's filter df to only the current day for VWAP
        current_day = lookback_df['time'].iloc[-1].date()
        daily_df = lookback_df[lookback_df['time'].dt.date == current_day]
        
        if len(daily_df) < 2:
            return None
            
        vwap = calculate_vwap(daily_df)
        adx = calculate_adx(lookback_df['high'], lookback_df['low'], lookback_df['close'], self.adx_period)
        
        current_adx = adx.iloc[-1]
        current_vwap = vwap.iloc[-1]
        
        if pd.isna(current_adx) or pd.isna(current_vwap):
            return None
            
        # Range filter relaxed to allow more trades
        if current_adx >= 30:
            return None
            
        latest_closed = daily_df.iloc[-1]
        
        # Fade extreme deviations: relaxed to 0.0015
        deviation = latest_closed['close'] - current_vwap
        
        is_buy = deviation < -0.0015
        is_sell = deviation > 0.0015
        
        if is_buy:
            sl = latest_closed['close'] - 0.0020
            tp = current_vwap
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
            sl = latest_closed['close'] + 0.0020
            tp = current_vwap
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
