import pandas as pd
from src.strategy.fvg_retest import FVGRetestStrategy

def test_fvg_retest_buy():
    strategy = FVGRetestStrategy(symbol="EURUSD")
    
    # 5 bars total (1 to 4 are closed, 5 is forming)
    data = {
        'time': range(5),
        'open': [1.1000, 1.1000, 1.1050, 1.1100, 1.1060],
        'high': [1.1010, 1.1010, 1.1090, 1.1150, 1.1100],
        'low': [1.0990, 1.0990, 1.1040, 1.1090, 1.1030],
        'close': [1.1000, 1.1000, 1.1080, 1.1140, 1.1050]
    }
    
    # c1 = index 0 (high 1.1010)
    # c3 = index 2 (low 1.1040)
    # FVG gap = 1.1040 - 1.1010 = 0.0030
    # latest_closed = index 3, wait I need 4 closed bars
    # Let's adjust:
    # df.iloc[-4] = c1
    # df.iloc[-3] = c2
    # df.iloc[-2] = c3
    # df.iloc[-1] = latest_closed
    
    data = {
        'time': range(6),
        'open': [1.10, 1.1000, 1.1050, 1.1100, 1.1050, 1.10],
        'high': [1.10, 1.1010, 1.1090, 1.1150, 1.1100, 1.10],
        'low': [1.10, 1.0990, 1.1040, 1.1080, 1.1030, 1.10],
        'close': [1.10, 1.1000, 1.1080, 1.1140, 1.1050, 1.10]
    }
    # c1 (idx 1): high 1.1010
    # c2 (idx 2): whatever
    # c3 (idx 3): low 1.1080
    # FVG is 1.1010 to 1.1080
    # latest_closed (idx 4): low 1.1030 (dips into FVG), close 1.1050 (above c1 high)
    
    df = pd.DataFrame(data)
    signal = strategy.analyze(df)
    
    assert signal is not None
    assert signal.side == "BUY"
