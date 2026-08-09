import pandas as pd
from datetime import datetime
from src.strategy.asian_range_scalp import AsianRangeScalpStrategy

def test_asian_range_scalp_buy():
    strategy = AsianRangeScalpStrategy(symbol="EURUSD")
    
    times = pd.date_range("2023-01-01 00:00:00", periods=30, freq="h")
    data = {
        'time': times,
        'open': [1.10]*30,
        'high': [1.12]*30,
        'low': [1.08]*30,
        'close': [1.10]*30
    }
    
    # Set up a buy scenario in Asian session (hour 4)
    data['close'][28] = 1.081 # Near low
    data['time'] = list(data['time'])
    data['time'][28] = datetime(2023, 1, 2, 4, 0, 0)
    
    df = pd.DataFrame(data)
    signal = strategy.analyze(df)
    
    assert signal is not None
    assert signal.side == "BUY"

def test_asian_range_scalp_no_signal_outside_session():
    strategy = AsianRangeScalpStrategy(symbol="EURUSD")
    
    times = pd.date_range("2023-01-01 12:00:00", periods=30, freq="h")
    data = {
        'time': times,
        'open': [1.10]*30,
        'high': [1.12]*30,
        'low': [1.08]*30,
        'close': [1.10]*30
    }
    
    # Set up a buy scenario but in NY session (hour 15)
    data['close'][28] = 1.081 # Near low
    data['time'] = list(data['time'])
    data['time'][28] = datetime(2023, 1, 2, 15, 0, 0)
    
    df = pd.DataFrame(data)
    signal = strategy.analyze(df)
    
    assert signal is None
