import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_supertrend, calculate_adx

class SupertrendPullbackStrategy:
    def __init__(self, symbol: str, st_period: int = 10, st_multi: float = 3.0, adx_period: int = 14):
        self.symbol = symbol
        self.st_period = st_period
        self.st_multi = st_multi
        self.adx_period = adx_period
        self.strategy_id = "SUPERTREND_PULLBACK"
        self.min_bars = max(self.st_period, self.adx_period) + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        lookback_df = df.iloc[:-1] # Remove forming bar
        
        st_df = calculate_supertrend(lookback_df, self.st_period, self.st_multi)
        adx = calculate_adx(lookback_df['high'], lookback_df['low'], lookback_df['close'], self.adx_period)
        
        current_adx = adx.iloc[-1]
        
        if pd.isna(current_adx) or pd.isna(st_df['supertrend'].iloc[-1]):
            return None
            
        # Trend filter relaxed
        if current_adx <= 20:
            return None
            
        latest_closed = lookback_df.iloc[-1]
        current_st = st_df['supertrend'].iloc[-1]
        current_dir = st_df['direction'].iloc[-1]
        
        # Pullback: Close is near the supertrend line but hasn't flipped it
        is_buy = (current_dir == 1) and (latest_closed['low'] <= current_st + 0.0010) and (latest_closed['close'] > current_st)
        is_sell = (current_dir == -1) and (latest_closed['high'] >= current_st - 0.0010) and (latest_closed['close'] < current_st)
        
        if is_buy:
            sl = current_st - 0.0020
            tp = latest_closed['close'] + 0.0060
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
            sl = current_st + 0.0020
            tp = latest_closed['close'] - 0.0060
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
