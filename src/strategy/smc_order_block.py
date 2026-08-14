import pandas as pd
from typing import Optional
from src.common.messages import SignalMessage, MessageHeader

class SMCOrderBlockStrategy:
    def __init__(self, symbol: str, lookback: int = 50):
        self.symbol = symbol
        self.lookback = lookback
        self.strategy_id = "SMC_ORDER_BLOCK"
        self.min_bars = self.lookback + 2

    def analyze(self, df: pd.DataFrame) -> Optional[SignalMessage]:
        if len(df) < self.min_bars:
            return None
            
        lookback_df = df.iloc[-self.lookback-2:-1]  # Exclude forming bar
        latest_closed = lookback_df.iloc[-1]
        
        # Dynamic gap threshold to qualify as an institutional displacement
        min_gap = 1.00 if "GOLD" in self.symbol or "XAU" in self.symbol else (0.10 if "SILVER" in self.symbol or "XAG" in self.symbol else 0.0010)
        sl_buffer = 1.50 if "GOLD" in self.symbol or "XAU" in self.symbol else (0.15 if "SILVER" in self.symbol or "XAG" in self.symbol else 0.0015)
        
        # Find the most recent FVG to identify displacement and its corresponding Order Block
        ob_long = None
        ob_short = None
        
        for i in range(len(lookback_df) - 4, 1, -1):
            c1 = lookback_df.iloc[i-2]
            c2 = lookback_df.iloc[i-1]
            c3 = lookback_df.iloc[i]
            
            # Check Bullish FVG
            bullish_fvg_gap = c3['low'] - c1['high']
            if bullish_fvg_gap >= min_gap:
                # Find the last bearish candle before c1
                for j in range(i-2, -1, -1):
                    if lookback_df.iloc[j]['close'] < lookback_df.iloc[j]['open']:
                        ob = lookback_df.iloc[j]
                        # Check if mitigated
                        mitigated = False
                        for k in range(i+1, len(lookback_df) - 1):
                            if lookback_df.iloc[k]['low'] <= ob['high']:
                                mitigated = True
                                break
                        if not mitigated:
                            ob_long = ob
                        break
                if ob_long is not None:
                    break
                    
            # Check Bearish FVG
            bearish_fvg_gap = c1['low'] - c3['high']
            if bearish_fvg_gap >= min_gap:
                # Find the last bullish candle before c1
                for j in range(i-2, -1, -1):
                    if lookback_df.iloc[j]['close'] > lookback_df.iloc[j]['open']:
                        ob = lookback_df.iloc[j]
                        # Check if mitigated
                        mitigated = False
                        for k in range(i+1, len(lookback_df) - 1):
                            if lookback_df.iloc[k]['high'] >= ob['low']:
                                mitigated = True
                                break
                        if not mitigated:
                            ob_short = ob
                        break
                if ob_short is not None:
                    break
                    
        # Check Mitigation (Entry trigger)
        if ob_long is not None:
            # Price tapped the OB this candle and closed bullish
            if latest_closed['low'] <= ob_long['high'] and latest_closed['close'] > latest_closed['open']:
                sl = ob_long['low'] - sl_buffer
                risk = latest_closed['close'] - sl
                tp = latest_closed['close'] + risk * 2.0
                return SignalMessage(
                    header=MessageHeader(source_component="strategy", message_type="Signal"),
                    symbol=self.symbol,
                    side="BUY",
                    strategy_id=self.strategy_id,
                    suggested_entry_price=latest_closed['close'],
                    suggested_sl_price=sl,
                    suggested_tp_price=tp
                )
                
        if ob_short is not None:
            # Price tapped the OB this candle and closed bearish
            if latest_closed['high'] >= ob_short['low'] and latest_closed['close'] < latest_closed['open']:
                sl = ob_short['high'] + sl_buffer
                risk = sl - latest_closed['close']
                tp = latest_closed['close'] - risk * 2.0
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
