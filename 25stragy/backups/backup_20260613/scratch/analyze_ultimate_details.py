import pandas as pd
import numpy as np
import os

def analyze():
    csv_path = r'C:\25stragy\backtest_results\v8_multiindex_trades.csv'
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} does not exist.")
        return

    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')

    print("="*80)
    # 1. Total & Index-wise summary
    print("SUMMARY BY INDEX:")
    indices = df['index'].unique()
    for idx in indices:
        sub = df[df['index'] == idx]
        total_pnl = sub['pnl_rs'].sum()
        trades = len(sub)
        wr = 100 * sub['won'].mean()
        
        # Calculate daily curve for drawdown
        daily_pnl = sub.groupby('date')['pnl_rs'].sum()
        cum_pnl = daily_pnl.cumsum()
        drawdown = (cum_pnl - cum_pnl.cummax()).min()
        
        print(f"  {idx:<12} | Trades: {trades:>4} | Win Rate: {wr:>4.1f}% | Net PnL: Rs.{total_pnl:>+12,.2f} | Max Drawdown: Rs.{drawdown:>+10,.2f}")

    print("\n" + "="*80)
    # 2. Monthly PnL per Index
    print("MONTHLY PnL BREAKDOWN PER INDEX:")
    monthly_idx = df.groupby(['month', 'index'])['pnl_rs'].sum().unstack(fill_value=0)
    print(monthly_idx.to_string())

    print("\n" + "="*80)
    # 3. Capital Deployed per Trade / Day
    # Capital per trade = entry_price * lot_size * lots
    # Let's map lot_size per index
    lot_sizes = {'NIFTY': 75, 'BANKNIFTY': 15, 'FINNIFTY': 40, 'SENSEX': 10}
    df['lot_size'] = df['index'].map(lot_sizes)
    df['capital_used'] = df['entry_price'] * df['lot_size'] * df['lots']

    # Daily capital used is the sum of capital_used for active trades at any one point. 
    # Since these are sequential/parallel option buys, we can look at the max single-trade capital 
    # and the sum of capital deployed per day.
    daily_cap = df.groupby('date')['capital_used'].agg(['sum', 'max', 'min'])
    print("DAILY CAPITAL UTILIZATION STATS:")
    print(f"  Average Capital Deployed per Day : Rs. {daily_cap['sum'].mean():,.2f}")
    print(f"  Maximum Capital Deployed in a Day: Rs. {daily_cap['sum'].max():,.2f}")
    print(f"  Minimum Capital Deployed in a Day: Rs. {daily_cap['sum'].min():,.2f}")
    print(f"  Average Single-Trade Sizing      : Rs. {df['capital_used'].mean():,.2f}")
    print(f"  Maximum Single-Trade Sizing      : Rs. {df['capital_used'].max():,.2f}")

if __name__ == '__main__':
    analyze()
