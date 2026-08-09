import pandas as pd
import pytest
from unittest.mock import patch
from src.strategy.mean_reversion import MeanReversionStrategy

def test_mean_reversion_buy():
    strategy = MeanReversionStrategy(symbol="EURUSD", rsi_period=14, adx_period=14)
    # We need at least min_bars (30) to bypass the length check
    data = {'time': range(30), 'open': [1.1]*30, 'high': [1.11]*30, 'low': [1.09]*30, 'close': [1.1]*30}
    df = pd.DataFrame(data)
    
    with patch('src.strategy.mean_reversion.calculate_rsi') as mock_rsi, \
         patch('src.strategy.mean_reversion.calculate_adx') as mock_adx:
        
        # Mock RSI to be oversold (e.g. 25) at iloc[-2]
        mock_rsi.return_value = pd.Series([50]*28 + [25, 50])
        # Mock ADX to be ranging (e.g. 15) at iloc[-2]
        mock_adx.return_value = pd.Series([15]*30)
        
        signal = strategy.analyze(df)
        assert signal is not None
        assert signal.side == "BUY"

def test_mean_reversion_no_signal_trending():
    strategy = MeanReversionStrategy(symbol="EURUSD", rsi_period=14, adx_period=14)
    data = {'time': range(30), 'open': [1.1]*30, 'high': [1.11]*30, 'low': [1.09]*30, 'close': [1.1]*30}
    df = pd.DataFrame(data)
    
    with patch('src.strategy.mean_reversion.calculate_rsi') as mock_rsi, \
         patch('src.strategy.mean_reversion.calculate_adx') as mock_adx:
        
        mock_rsi.return_value = pd.Series([50]*28 + [25, 50])
        # ADX > 20 means trending, mean reversion shouldn't fire
        mock_adx.return_value = pd.Series([25]*30)
        
        signal = strategy.analyze(df)
        assert signal is None
