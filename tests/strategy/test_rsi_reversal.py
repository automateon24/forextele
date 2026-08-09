import pandas as pd
import pytest
from unittest.mock import patch
from src.strategy.rsi_reversal import RSIReversalStrategy

def test_rsi_reversal_buy():
    strategy = RSIReversalStrategy(symbol="EURUSD")
    data = {'time': range(40), 'open': [1.1]*40, 'high': [1.11]*40, 'low': [1.09]*40, 'close': [1.1]*40}
    df = pd.DataFrame(data)
    
    with patch('src.strategy.rsi_reversal.calculate_rsi') as mock_rsi, \
         patch('src.strategy.rsi_reversal.calculate_adx') as mock_adx:
        
        mock_rsi.return_value = pd.Series([50]*38 + [25])
        mock_adx.return_value = pd.Series([15]*39)
        
        signal = strategy.analyze(df)
        assert signal is not None
        assert signal.side == "BUY"

def test_rsi_reversal_adx_filter():
    strategy = RSIReversalStrategy(symbol="EURUSD")
    data = {'time': range(40), 'open': [1.1]*40, 'high': [1.11]*40, 'low': [1.09]*40, 'close': [1.1]*40}
    df = pd.DataFrame(data)
    
    with patch('src.strategy.rsi_reversal.calculate_rsi') as mock_rsi, \
         patch('src.strategy.rsi_reversal.calculate_adx') as mock_adx:
        
        mock_rsi.return_value = pd.Series([50]*38 + [25])
        mock_adx.return_value = pd.Series([25]*39) # ADX too high
        
        signal = strategy.analyze(df)
        assert signal is None
