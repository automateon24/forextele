import pandas as pd
from datetime import datetime
from src.strategy.london_session_scalp import LondonSessionScalpStrategy

def test_london_session_scalp_buy():
    strategy = LondonSessionScalpStrategy(symbol="EURUSD", lookback=4)
    times = pd.date_range("2023-01-01 00:00:00", periods=20, freq="h")
    data = {
        'time': times,
        'open': [1.10]*20,
        'high': [1.11]*20,
        'low': [1.09]*20,
        'close': [1.10]*20
    }
    
    data['time'] = list(data['time'])
    data['time'][-2] = datetime(2023, 1, 1, 8, 0, 0)
    data['close'][-2] = 1.12 # Breakout
    
    df = pd.DataFrame(data)
    signal = strategy.analyze(df)
    assert signal is not None
    assert signal.side == "BUY"
