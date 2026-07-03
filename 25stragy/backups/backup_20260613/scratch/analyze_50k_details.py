import pandas as pd
import numpy as np
import os

def analyze():
    csv_path = r'C:\25stragy\backtest_results\strict_50k_trades.csv'
    if not os.path.exists(csv_path):
        print("CSV not found.")
        return

    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')

    print("="*80)
    print("50K PER INDEX PERFORMANCE SUMMARY:")
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
    print("50K MONTHLY PnL BREAKDOWN PER INDEX:")
    monthly_idx = df.groupby(['month', 'index'])['pnl_rs'].sum().unstack(fill_value=0)
    print(monthly_idx.to_string())

    print("\n" + "="*80)
    print("50K DAILY CAPITAL UTILIZATION STATS:")
    lot_sizes = {'NIFTY': 75, 'BANKNIFTY': 15, 'FINNIFTY': 40, 'SENSEX': 10}
    df['lot_size'] = df['index'].map(lot_sizes)
    df['capital_used'] = df['entry_price'] * df['lot_size'] * df['lots']

    daily_cap = df.groupby('date')['capital_used'].agg(['sum', 'max', 'min'])
    print(f"  Average Daily Deployed Capital    : Rs. {daily_cap['sum'].mean():,.2f}")
    print(f"  Max Capital Deployed in a Day     : Rs. {daily_cap['sum'].max():,.2f}")
    print(f"  Min Capital Deployed in a Day     : Rs. {daily_cap['sum'].min():,.2f}")
    
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

    # Portfolio combined drawdown
    daily_pnl = df.groupby('date')['pnl_rs'].sum()
    cum_pnl = daily_pnl.cumsum()
    portfolio_drawdown = (cum_pnl - cum_pnl.cummax()).min()
    print(f"\n  Combined Portfolio Max Drawdown (50k): Rs. {portfolio_drawdown:,.2f}")

if __name__ == '__main__':
    analyze()
