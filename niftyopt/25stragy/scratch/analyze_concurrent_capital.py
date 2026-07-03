import pandas as pd
import numpy as np
import os

def analyze_concurrent():
    csv_path = r'C:\25stragy\backtest_results\v8_multiindex_trades.csv'
    if not os.path.exists(csv_path):
        return

    df = pd.read_csv(csv_path)
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    
    lot_sizes = {'NIFTY': 75, 'BANKNIFTY': 15, 'FINNIFTY': 40, 'SENSEX': 10}
    df['lot_size'] = df['index'].map(lot_sizes)
    df['capital_used'] = df['entry_price'] * df['lot_size'] * df['lots']

    # We want to find the maximum concurrent capital at any minute.
    # To do this, we can generate a series of minutes and check active trades.
    # A simpler way is to find all unique entry and exit times, sort them, and track active capital.
    events = []
    for _, row in df.iterrows():
        events.append((row['entry_time'], row['capital_used']))
        events.append((row['exit_time'], -row['capital_used']))
        
    events.sort(key=lambda x: x[0])
    
    current_cap = 0
    max_concurrent_cap = 0
    max_concurrent_cap_date = None
    
    for time, cap in events:
        current_cap += cap
        if current_cap > max_concurrent_cap:
            max_concurrent_cap = current_cap
            max_concurrent_cap_date = time
            
    print(f"Maximum concurrent capital locked at any single minute: Rs. {max_concurrent_cap:,.2f} on {max_concurrent_cap_date}")

if __name__ == '__main__':
    analyze_concurrent()
