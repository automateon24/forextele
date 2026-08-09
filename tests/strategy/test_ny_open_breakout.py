import pandas as pd
from datetime import datetime
from src.strategy.ny_open_breakout import NYOpenBreakoutStrategy

def test_ny_open_breakout_buy():
    strategy = NYOpenBreakoutStrategy(symbol="EURUSD", lookback=5)
    
    times = pd.date_range("2023-01-01 08:00:00", periods=10, freq="h")
    data = {
        'time': times,
        'open': [1.10]*10,
        'high': [1.12]*10,
        'low': [1.08]*10,
        'close': [1.10]*10
    }
    
    # NY session (14:00) breakout
    data['close'][-2] = 1.13 # Breakout above 1.12
    data['time'] = list(data['time'])
    data['time'][-2] = datetime(2023, 1, 1, 14, 0, 0)
    
    df = pd.DataFrame(data)
    signal = strategy.analyze(df)
    
    assert signal is not None
    assert signal.side == "BUY"
