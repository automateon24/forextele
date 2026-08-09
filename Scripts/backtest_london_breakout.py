import sys
import os
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

# Ensure we can import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.strategy.london_breakout import LondonBreakoutStrategy
from src.strategy.market_data import init_mt5

def fetch_data_and_test():
    print("Initializing MT5...")
    if not init_mt5():
        print("Failed to initialize MT5")
        return

    symbol = "EURUSD"
    timeframe = mt5.TIMEFRAME_H1
    
    # 1 month ago
    utc_from = datetime.now() - timedelta(days=30)
    utc_to = datetime.now()
    
    print(f"Fetching 1 month of {symbol} H1 data from MT5...")
    rates = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)
    
    if rates is None or len(rates) == 0:
        print("No data retrieved from MT5.")
        mt5.shutdown()
        return
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    print(f"Fetched {len(df)} candles.")
    
    strategy = LondonBreakoutStrategy(symbol=symbol, lookback=10)
    
    signals = []
    print("Running LondonBreakoutStrategy over historical data...")
    # Simulate streaming data by feeding it window by window
    for i in range(strategy.lookback + 1, len(df)):
        window = df.iloc[i - strategy.lookback - 1 : i]
        signal = strategy.analyze(window)
        if signal:
            signals.append(signal)
            
    print(f"Total Signals Generated in 1 Month: {len(signals)}")
    if signals:
        print(f"Most Recent Signal: {signals[-1].model_dump()}")
        
    mt5.shutdown()

if __name__ == "__main__":
    fetch_data_and_test()
