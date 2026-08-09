import pandas as pd
from unittest.mock import patch
from src.strategy.supertrend_pullback import SupertrendPullbackStrategy

def test_supertrend_pullback_buy():
    strategy = SupertrendPullbackStrategy(symbol="EURUSD")
    data = {'time': range(30), 'open': [1.1]*30, 'high': [1.11]*30, 'low': [1.09]*30, 'close': [1.1020]*30}
    
    # Pullback touches 1.1000
    data['low'][-2] = 1.1000
    data['close'][-2] = 1.1005
    df = pd.DataFrame(data)
    
    with patch('src.strategy.supertrend_pullback.calculate_adx') as mock_adx, \
         patch('src.strategy.supertrend_pullback.calculate_supertrend') as mock_st:
        
        mock_adx.return_value = pd.Series([30]*29) # Trending
        
        # Supertrend is 1.1000, direction is 1 (UP)
        st_df = pd.DataFrame({'supertrend': [1.1000]*29, 'direction': [1]*29})
        mock_st.return_value = st_df
        
        signal = strategy.analyze(df)
        assert signal is not None
        assert signal.side == "BUY"
