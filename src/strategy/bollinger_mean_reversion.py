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

        if pd.isna(upper.iloc[-1]) or pd.isna(lower.iloc[-1]) or pd.isna(adx.iloc[-1]):
            return None

        # ADX Gate: Only allow mean reversion when ADX < 20 (Ranging / Non-trending market)
        if adx.iloc[-1] >= 20.0:
            return None

        latest_closed = lookback_df.iloc[-1]
        
        # Symbol-aware buffer
        if "GOLD" in self.symbol or "XAU" in self.symbol:
            buffer = 1.50
        else:
            buffer = 0.0020
        
        # Touch or cross of lower band -> BUY; upper band -> SELL
        is_buy = latest_closed['low'] <= lower.iloc[-1]
        is_sell = latest_closed['high'] >= upper.iloc[-1]
        
        if is_buy:
            sl = min(latest_closed['low'], lower.iloc[-1]) - buffer
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
        elif is_sell:
            sl = max(latest_closed['high'], upper.iloc[-1]) + buffer
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
