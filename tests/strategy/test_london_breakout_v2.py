import pandas as pd
from datetime import datetime
from unittest.mock import patch
from src.strategy.london_breakout_v2 import LondonBreakoutV2Strategy

def test_london_breakout_v2_buy():
    strategy = LondonBreakoutV2Strategy(symbol="EURUSD", lookback=4)
    
    times = pd.date_range("2023-01-01 04:00:00", periods=20, freq="h")
    data = {
        'time': times,
        'open': [1.10]*20,
        'high': [1.12]*20,
        'low': [1.08]*20,
        'close': [1.10]*20
    }
    
    # 08:00 session (index 18 is closed candle for current bar 19)
    data['time'] = list(data['time'])
    data['time'][-2] = datetime(2023, 1, 1, 8, 0, 0)
    data['close'][-2] = 1.13 # Breakout
    
    df = pd.DataFrame(data)
    
    with patch('src.strategy.london_breakout_v2.calculate_atr') as mock_atr:
        mock_atr.return_value = pd.Series([0.02]*20) # Range size is 0.04 > 0.01 (0.5 ATR)
        
        signal = strategy.analyze(df)
        assert signal is not None
        assert signal.side == "BUY"
