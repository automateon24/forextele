import pandas as pd
import pytest
import os
import sys

# Ensure tests can import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.strategy.london_breakout import LondonBreakoutStrategy

def test_london_breakout_buy():
    strategy = LondonBreakoutStrategy(symbol="EURUSD", lookback=3)
    data = {
        'time': [1, 2, 3, 4],
        'open': [1.1, 1.1, 1.1, 1.1],
        'high': [1.11, 1.12, 1.10, 1.15],
        'low': [1.09, 1.08, 1.09, 1.11],
        'close': [1.1, 1.1, 1.1, 1.14]
    }
    df = pd.DataFrame(data)
    signal = strategy.analyze(df)
    assert signal is not None
    assert signal.side == "BUY"
    assert signal.suggested_sl_price == 1.08
    assert signal.suggested_tp_price == 1.14 + (1.14 - 1.08) * 2

def test_london_breakout_no_signal():
    strategy = LondonBreakoutStrategy(symbol="EURUSD", lookback=3)
    data = {
        'time': [1, 2, 3, 4],
        'open': [1.1, 1.1, 1.1, 1.1],
        'high': [1.11, 1.12, 1.10, 1.11],
        'low': [1.09, 1.08, 1.09, 1.09],
        'close': [1.1, 1.1, 1.1, 1.1]
    }
    df = pd.DataFrame(data)
    signal = strategy.analyze(df)
    assert signal is None
