import pandas as pd
import pytest
from src.strategy.smc_order_block import SMCOrderBlockStrategy

def test_smc_order_block_buy():
    strategy = SMCOrderBlockStrategy(symbol="EURUSD", lookback=10)
    
    # 12 bars total to pass length check (lookback + 2)
    # We want a strong rejection at the lowest low.
    lows = [1.15]*10
    lows[5] = 1.10 # This is the lowest low in the lookback
    
    data = {
        'time': range(12),
        'open': [1.15]*10 + [1.1001, 1.15], # iloc[-2] opens near the low
        'high': [1.16]*10 + [1.15, 1.16],
        'low': lows + [1.10, 1.14], # iloc[-2] sweeps the low (1.10)
        'close': [1.15]*10 + [1.14, 1.15] # iloc[-2] closes much higher (bullish rejection)
    }
    df = pd.DataFrame(data)
    
    signal = strategy.analyze(df)
    assert signal is not None
    assert signal.side == "BUY"
    assert signal.suggested_sl_price == 1.10 - 0.0010

def test_smc_order_block_no_signal():
    strategy = SMCOrderBlockStrategy(symbol="EURUSD", lookback=10)
    
    lows = [1.15]*10
    lows[5] = 1.10 # This is the lowest low in the lookback
    
    data = {
        'time': range(12),
        'open': [1.15]*10 + [1.14, 1.15],
        'high': [1.16]*10 + [1.15, 1.16],
        'low': lows + [1.12, 1.14], # iloc[-2] low is 1.12, far from 1.10
        'close': [1.15]*10 + [1.145, 1.15]
    }
    df = pd.DataFrame(data)
    
    signal = strategy.analyze(df)
    assert signal is None
