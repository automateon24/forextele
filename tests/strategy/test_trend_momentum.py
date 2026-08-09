import pandas as pd
import pytest
from unittest.mock import patch
from src.strategy.trend_momentum import TrendMomentumStrategy

def test_trend_momentum_buy():
    strategy = TrendMomentumStrategy(symbol="EURUSD", rsi_period=14, adx_period=14)
    data = {'time': range(30), 'open': [1.1]*30, 'high': [1.11]*30, 'low': [1.09]*30, 'close': [1.1]*30}
    df = pd.DataFrame(data)
    
    with patch('src.strategy.trend_momentum.calculate_rsi') as mock_rsi, \
         patch('src.strategy.trend_momentum.calculate_adx') as mock_adx:
        
        # Mock RSI to show strong upward momentum (>60)
        mock_rsi.return_value = pd.Series([50]*28 + [65, 50])
        # Mock ADX to show strong trend (>25)
        mock_adx.return_value = pd.Series([30]*30)
        
        signal = strategy.analyze(df)
        assert signal is not None
        assert signal.side == "BUY"

def test_trend_momentum_no_signal_ranging():
    strategy = TrendMomentumStrategy(symbol="EURUSD", rsi_period=14, adx_period=14)
    data = {'time': range(30), 'open': [1.1]*30, 'high': [1.11]*30, 'low': [1.09]*30, 'close': [1.1]*30}
    df = pd.DataFrame(data)
    
    with patch('src.strategy.trend_momentum.calculate_rsi') as mock_rsi, \
         patch('src.strategy.trend_momentum.calculate_adx') as mock_adx:
        
        mock_rsi.return_value = pd.Series([50]*28 + [65, 50])
        # ADX <= 25 means ranging, trend strategy shouldn't fire
        mock_adx.return_value = pd.Series([20]*30)
        
        signal = strategy.analyze(df)
        assert signal is None
