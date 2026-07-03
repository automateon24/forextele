import pandas as pd
import os

def analyze_portfolio_drawdown():
    csv_path = r'C:\25stragy\backtest_results\strict_trades.csv'
    if not os.path.exists(csv_path):
        return

    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    
    # Calculate daily portfolio PnL (sum of all indices)
    daily_pnl = df.groupby('date')['pnl_rs'].sum()
    cum_pnl = daily_pnl.cumsum()
    portfolio_drawdown = (cum_pnl - cum_pnl.cummax()).min()
    print(f"Combined Portfolio Max Drawdown (Strict Capital): Rs. {portfolio_drawdown:,.2f}")

if __name__ == '__main__':
    analyze_portfolio_drawdown()
