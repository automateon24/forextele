import pandas as pd
import os

def inspect():
    csv_path = r'C:\25stragy\backtest_results\strict_trades.csv'
    if not os.path.exists(csv_path):
        print("CSV not found.")
        return

    df = pd.read_csv(csv_path)
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    
    lot_sizes = {'NIFTY': 75, 'BANKNIFTY': 15, 'FINNIFTY': 40, 'SENSEX': 10}
    df['lot_size'] = df['index'].map(lot_sizes)
    df['capital_used'] = df['entry_price'] * df['lot_size'] * df['lots']

    # Let's inspect NIFTY on 2026-01-05
    target_time = pd.Timestamp('2026-01-05 14:01:00')
    active_trades = df[
        (df['index'] == 'NIFTY') &
        (df['entry_time'] <= target_time) &
        (df['exit_time'] > target_time)
    ]
    
    print("ACTIVE TRADES ON NIFTY AT 2026-01-05 14:01:00:")
    print(active_trades[['strategy', 'direction', 'entry_time', 'exit_time', 'entry_price', 'lots', 'capital_used']].to_string())
    print(f"Total concurrent capital: Rs. {active_trades['capital_used'].sum():,.2f}")

if __name__ == '__main__':
    inspect()
