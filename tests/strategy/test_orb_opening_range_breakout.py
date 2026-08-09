import pandas as pd
from datetime import datetime
from src.strategy.orb_opening_range_breakout import ORBOpeningRangeBreakoutStrategy

def test_orb_buy():
    strategy = ORBOpeningRangeBreakoutStrategy(symbol="EURUSD", lookback=4, max_range_pips=0.0050)
    
    times = pd.date_range("2023-01-01 00:00:00", periods=20, freq="h")
    data = {
        'time': times,
        'open': [1.10]*20,
        'high': [1.1020]*20,
        'low': [1.0990]*20,
        'close': [1.10]*20
    }
    
    # Target hour 12
    data['time'] = list(data['time'])
    data['time'][-2] = datetime(2023, 1, 1, 12, 0, 0)
    data['close'][-2] = 1.1030 # Breakout
    
    df = pd.DataFrame(data)
    
    signal = strategy.analyze(df)
    assert signal is not None
    assert signal.side == "BUY"
