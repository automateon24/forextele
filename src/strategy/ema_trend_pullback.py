import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_adx, calculate_ema

class EMATrendPullbackStrategy:
    def __init__(self, symbol: str, fast_ema: int = 20, slow_ema: int = 50, adx_period: int = 14):
        self.symbol = symbol
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.adx_period = adx_period
        self.strategy_id = "EMA_TREND_PULLBACK"
        self.min_bars = self.slow_ema + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        lookback_df = df.iloc[:-1] # Remove forming bar
        
        adx = calculate_adx(lookback_df['high'], lookback_df['low'], lookback_df['close'], self.adx_period)
        fast_line = calculate_ema(lookback_df['close'], self.fast_ema)
        slow_line = calculate_ema(lookback_df['close'], self.slow_ema)
        
        current_adx = adx.iloc[-1]
        
        if pd.isna(current_adx) or pd.isna(fast_line.iloc[-1]):
            return None
            
        # Trend filter
        if current_adx <= 25:
            return None
            
        latest_closed = lookback_df.iloc[-1]
        prev_closed = lookback_df.iloc[-2]
        
        # Pullback logic: Trend is up, price pulls back into the gap between fast and slow EMA, then rejects
        uptrend = fast_line.iloc[-1] > slow_line.iloc[-1]
        downtrend = fast_line.iloc[-1] < slow_line.iloc[-1]
        
        is_buy = uptrend and (latest_closed['low'] <= fast_line.iloc[-1]) and (latest_closed['close'] > fast_line.iloc[-1])
        is_sell = downtrend and (latest_closed['high'] >= fast_line.iloc[-1]) and (latest_closed['close'] < fast_line.iloc[-1])
        
        if "GOLD" in self.symbol or "XAU" in self.symbol:
            sl_buffer = 1.50
            tp_dist = 4.00
        else:
            sl_buffer = 0.0010
            tp_dist = 0.0050
            
        if is_buy:
            sl = slow_line.iloc[-1] - sl_buffer
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
        elif is_sell:
            sl = slow_line.iloc[-1] + sl_buffer
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
