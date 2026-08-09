import pandas as pd
from unittest.mock import patch
from src.strategy.vwap_mean_reversion import VWAPMeanReversionStrategy

def test_vwap_mean_reversion_buy():
    strategy = VWAPMeanReversionStrategy(symbol="EURUSD")
    
    times = pd.date_range("2023-01-01 00:00:00", periods=20, freq="h")
    data = {
        'time': times,
        'open': [1.10]*20,
        'high': [1.11]*20,
        'low': [1.09]*20,
        'close': [1.10]*20
    }
    
    # Large downward deviation
    data['close'][-2] = 1.096
    
    df = pd.DataFrame(data)
    
    with patch('src.strategy.vwap_mean_reversion.calculate_adx') as mock_adx, \
         patch('src.strategy.vwap_mean_reversion.calculate_vwap') as mock_vwap:
        
        mock_adx.return_value = pd.Series([15]*20) # Ranging
        mock_vwap.return_value = pd.Series([1.10]*19) # VWAP is 1.10
        # Dev is 1.096 - 1.100 = -0.0040 (which is < -0.0030)
        
        signal = strategy.analyze(df)
        assert signal is not None
        assert signal.side == "BUY"
