import pandas as pd
import numpy as np
import os

def analyze():
    # In scratch/test_ultimate_strict_capital.py we report metrics, but we didn't save the trades to a separate CSV.
    # Wait, did it save to backtest_results/v8_multiindex_trades.csv?
    # Yes! The patch ran the report_multi which saves the file to backtest_results/v8_multiindex_trades.csv!
    # Let's verify by parsing the csv which has 1,170 rows.
    csv_path = r'C:\25stragy\backtest_results\strict_trades.csv'
    if not os.path.exists(csv_path):
        print("CSV not found.")
        return

    df = pd.read_csv(csv_path)
    if len(df) != 1170:
        print(f"Warning: CSV has {len(df)} rows, expected 1170. Let's process it anyway.")

    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')

    print("="*80)
    print("INDEX PERFORMANCE SUMMARY (STRICT CAPITAL):")
    for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']:
        sub = df[df['index'] == idx]
        total_pnl = sub['pnl_rs'].sum()
        trades = len(sub)
        wr = 100 * sub['won'].mean()
        
        daily_pnl = sub.groupby('date')['pnl_rs'].sum()
        cum_pnl = daily_pnl.cumsum()
        drawdown = (cum_pnl - cum_pnl.cummax()).min()
        
        print(f"  {idx:<12} | Trades: {trades:>4} | Win Rate: {wr:>4.1f}% | Net PnL: Rs.{total_pnl:>+12,.2f} | Max Drawdown: Rs.{drawdown:>+10,.2f}")

    print("\n" + "="*80)
    print("MONTHLY PnL BREAKDOWN PER INDEX:")
    monthly_idx = df.groupby(['month', 'index'])['pnl_rs'].sum().unstack(fill_value=0)
    print(monthly_idx.to_string())

    print("\n" + "="*80)
    print("DAILY CAPITAL UTILIZATION STATS:")
    lot_sizes = {'NIFTY': 75, 'BANKNIFTY': 15, 'FINNIFTY': 40, 'SENSEX': 10}
    df['lot_size'] = df['index'].map(lot_sizes)
    df['capital_used'] = df['entry_price'] * df['lot_size'] * df['lots']

    daily_cap = df.groupby('date')['capital_used'].agg(['sum', 'max', 'min'])
    print(f"  Average Daily Deployed Capital    : Rs. {daily_cap['sum'].mean():,.2f}")
    print(f"  Max Capital Deployed in a Day     : Rs. {daily_cap['sum'].max():,.2f}")
    print(f"  Min Capital Deployed in a Day     : Rs. {daily_cap['sum'].min():,.2f}")
    
    # Calculate concurrent capital locked per minute to prove it never exceeds Rs. 150k per index
    for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']:
        sub = df[df['index'] == idx]
        events = []
        for _, row in sub.iterrows():
            events.append((pd.to_datetime(row['entry_time']), row['capital_used']))
            events.append((pd.to_datetime(row['exit_time']), -row['capital_used']))
        events.sort(key=lambda x: x[0])
        current_cap = 0
        max_concurrent_cap = 0
        for time, cap in events:
            current_cap += cap
            max_concurrent_cap = max(max_concurrent_cap, current_cap)
        print(f"  Max Concurrent Capital used by {idx:<10}: Rs. {max_concurrent_cap:,.2f}")

if __name__ == '__main__':
    analyze()
