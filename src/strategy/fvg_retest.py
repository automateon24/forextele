import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

class FVGRetestStrategy:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.strategy_id = "FVG_RETEST"
        self.min_bars = 5 # 3 for FVG formation + 1 for retest + 1 forming

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        lookback_df = df.iloc[:-1] # Remove forming bar
        
        c1 = lookback_df.iloc[-4]
        c2 = lookback_df.iloc[-3]
        c3 = lookback_df.iloc[-2]
        latest_closed = lookback_df.iloc[-1]
        
        # Bullish FVG (c1 high < c3 low)
        bullish_fvg = c1['high'] < c3['low']
        bullish_fvg_gap = c3['low'] - c1['high']
        
        # Bearish FVG (c1 low > c3 high)
        bearish_fvg = c1['low'] > c3['high']
        bearish_fvg_gap = c1['low'] - c3['high']
        
        # Retest logic: latest closed candle enters the gap
        is_buy = bullish_fvg and (bullish_fvg_gap > 0.0005) and (latest_closed['low'] <= c3['low']) and (latest_closed['close'] > c1['high'])
        is_sell = bearish_fvg and (bearish_fvg_gap > 0.0005) and (latest_closed['high'] >= c3['high']) and (latest_closed['close'] < c1['low'])
        
        if is_buy:
            sl = c1['low'] - 0.0010
            tp = latest_closed['close'] + (latest_closed['close'] - sl) * 2
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
            sl = c1['high'] + 0.0010
            tp = latest_closed['close'] - (sl - latest_closed['close']) * 2
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
