import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader
from src.common.indicators import calculate_rsi, calculate_adx

class TrendMomentumStrategy:
    def __init__(self, symbol: str, rsi_period: int = 14, adx_period: int = 14, sl_dist: Optional[float] = None, tp_dist: Optional[float] = None):
        self.symbol = symbol
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.sl_dist_override = sl_dist
        self.tp_dist_override = tp_dist
        self.strategy_id = "TREND_MOMENTUM"
        self.min_bars = max(self.rsi_period, self.adx_period) * 2 + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        latest_closed = df.iloc[-2]
        
        # Time-Gate Optimization Filter (Trend Momentum H1 optimized for 08:00-15:00 UTC)
        current_hour = df.iloc[-1]['time'].hour
        if "GOLD" in self.symbol or "XAU" in self.symbol:
            if current_hour < 8 or current_hour > 15:
                return None
        
        
        rsi = calculate_rsi(df['close'], self.rsi_period)
        adx = calculate_adx(df['high'], df['low'], df['close'], self.adx_period)
        
        latest_rsi = rsi.iloc[-2]
        
        from src.common.indicators import calculate_ema
        ema20 = calculate_ema(df['close'], 20)
        latest_ema20 = ema20.iloc[-2]
        
        if pd.isna(latest_rsi) or pd.isna(latest_ema20):
            return None
            
        if self.sl_dist_override is not None and self.tp_dist_override is not None:
            sl_dist = self.sl_dist_override
            tp_dist = self.tp_dist_override
        else:
            if "GOLD" in self.symbol or "XAU" in self.symbol:
                sl_dist = 3.00
                tp_dist = 4.50
            elif "JPY" in self.symbol:
                sl_dist = 0.30
                tp_dist = 0.45
            else:
                sl_dist = 0.0030
                tp_dist = 0.0045
            
        # Inverted logic: Mean Reversion off extremes (Buy Oversold, Sell Overbought)
        if latest_rsi < 42 and latest_closed['close'] < latest_ema20:
            sl = latest_closed['close'] - sl_dist
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
        # Inverted logic: Mean Reversion off extremes (Buy Oversold, Sell Overbought)
        elif latest_rsi > 58 and latest_closed['close'] > latest_ema20:
            sl = latest_closed['close'] + sl_dist
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
