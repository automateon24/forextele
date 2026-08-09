import pandas as pd
import pytest
from unittest.mock import patch
from src.strategy.ema_trend_pullback import EMATrendPullbackStrategy

def test_ema_pullback_buy():
    strategy = EMATrendPullbackStrategy(symbol="EURUSD")
    data = {'time': range(60), 'open': [1.1]*60, 'high': [1.11]*60, 'low': [1.09]*60, 'close': [1.105]*60}
    # Latest close reclaims fast line
    data['low'][-2] = 1.09
    data['close'][-2] = 1.105
    
    df = pd.DataFrame(data)
    
    with patch('src.strategy.ema_trend_pullback.calculate_adx') as mock_adx, \
         patch('src.strategy.ema_trend_pullback.calculate_ema') as mock_ema:
        
        mock_adx.return_value = pd.Series([30]*59) # Strong trend
        
        def mock_ema_func(series, period):
            if period == 20: # Fast
                return pd.Series([1.10]*59)
            return pd.Series([1.08]*59) # Slow
            
        mock_ema.side_effect = mock_ema_func
        
        signal = strategy.analyze(df)
        assert signal is not None
        assert signal.side == "BUY"
