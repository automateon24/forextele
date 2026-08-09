import pandas as pd
import pytest
from unittest.mock import patch
from src.strategy.bollinger_mean_reversion import BollingerMeanReversionStrategy

def test_bollinger_mean_reversion_buy():
    strategy = BollingerMeanReversionStrategy(symbol="EURUSD")
    data = {'time': range(30), 'open': [1.1]*30, 'high': [1.11]*30, 'low': [1.09]*30, 'close': [1.10]*30}
    data['low'][-2] = 1.05
    data['close'][-2] = 1.07
    df = pd.DataFrame(data)
    
    with patch('src.strategy.bollinger_mean_reversion.calculate_adx') as mock_adx, \
         patch('src.strategy.bollinger_mean_reversion.calculate_bollinger_bands') as mock_bb:
        
        mock_adx.return_value = pd.Series([15]*29) # Ranging
        
        # Upper, middle, lower
        upper = pd.Series([1.15]*29)
        middle = pd.Series([1.10]*29)
        lower = pd.Series([1.06]*29)
        mock_bb.return_value = (upper, middle, lower)
        
        signal = strategy.analyze(df)
        assert signal is not None
        assert signal.side == "BUY"
