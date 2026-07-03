import pandas as pd
import numpy as np
import os

def analyze_index_concurrent():
    csv_path = r'C:\25stragy\backtest_results\v8_multiindex_trades.csv'
    if not os.path.exists(csv_path):
        return

    df = pd.read_csv(csv_path)
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    
    lot_sizes = {'NIFTY': 75, 'BANKNIFTY': 15, 'FINNIFTY': 40, 'SENSEX': 10}
    df['lot_size'] = df['index'].map(lot_sizes)
    df['capital_used'] = df['entry_price'] * df['lot_size'] * df['lots']

    for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']:
        sub = df[df['index'] == idx]
        events = []
        for _, row in sub.iterrows():
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
                
        print(f"Index: {idx:<12} | Max Concurrent Capital: Rs. {max_concurrent_cap:>10,.2f} on {max_concurrent_cap_date}")

if __name__ == '__main__':
    analyze_index_concurrent()
