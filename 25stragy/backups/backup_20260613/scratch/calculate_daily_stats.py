import pandas as pd
import numpy as np

csv_path = r"C:\25stragy\backtest_results\aggressive_100k_trades.csv"
df = pd.read_csv(csv_path)
df['date'] = pd.to_datetime(df['date'])

# Group by date to get daily PnL
daily_pnl = df.groupby('date')['pnl_rs'].sum()
all_days = len(daily_pnl)

# Average Daily Gain
avg_daily_gain = daily_pnl.mean()

# Best and Worst Days
max_daily_gain = daily_pnl.max()
min_daily_gain = daily_pnl.min()

# Cumulative equity curve
cumulative_pnl = daily_pnl.cumsum()
running_max = cumulative_pnl.cummax()
drawdown = cumulative_pnl - running_max
max_portfolio_drawdown = drawdown.min()

print("==================================================")
print("             DAILY PERFORMANCE STATS              ")
print("==================================================")
print(f"Total Trading Days         : {all_days}")
print(f"Average Daily Gain (All)   : Rs. {avg_daily_gain:+,.2f} per day")
print(f"Maximum Daily Profit (Best): Rs. {max_daily_gain:+,.2f}")
print(f"Maximum Daily Loss (Worst) : Rs. {min_daily_gain:+,.2f}")
print(f"Max Portfolio Drawdown     : Rs. {max_portfolio_drawdown:+,.2f}")
print("==================================================\n")

print("=== DAILY PNL STATISTICS BY INDEX ===")
for idx in sorted(df['index'].unique()):
    idx_df = df[df['index'] == idx]
    idx_daily = idx_df.groupby('date')['pnl_rs'].sum()
    idx_cum = idx_daily.cumsum()
    idx_running_max = idx_cum.cummax()
    idx_dd = idx_cum - idx_running_max
    
    print(f"Index: {idx}")
    print(f"  Active Trading Days      : {len(idx_daily)}")
    print(f"  Average Daily Gain       : Rs. {idx_daily.mean():+,.2f} per day")
    print(f"  Maximum Daily Profit     : Rs. {idx_daily.max():+,.2f}")
    print(f"  Maximum Daily Loss       : Rs. {idx_daily.min():+,.2f}")
    print(f"  Max Cumulative Drawdown  : Rs. {idx_dd.min():+,.2f}")
    print("-" * 50)
