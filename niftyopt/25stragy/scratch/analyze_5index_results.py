import pandas as pd
import numpy as np

csv_path = r"C:\25stragy\backtest_results\aggressive_100k_trades.csv"
df = pd.read_csv(csv_path)
df['date'] = pd.to_datetime(df['date'])

print("=== COMBINED PORTFOLIO RESULTS (5 INDICES) ===")
total_trades = len(df)
overall_win_rate = 100 * df['won'].mean()
total_pnl = df['pnl_rs'].sum()

# Daily stats for drawdown
daily_pnl = df.groupby('date')['pnl_rs'].sum()
cumulative_pnl = daily_pnl.cumsum()
max_drawdown = (cumulative_pnl - cumulative_pnl.cummax()).min()

print(f"Total Trades: {total_trades}")
print(f"Win Rate: {overall_win_rate:.2f}%")
print(f"Total Portfolio Net Profit: Rs. {total_pnl:+,.2f}")
print(f"Max Portfolio Drawdown (Daily Close-to-Close): Rs. {max_drawdown:+,.2f}")

print("\n=== PER INDEX BREAKDOWN ===")
for idx in sorted(df['index'].unique()):
    idx_df = df[df['index'] == idx]
    idx_daily = idx_df.groupby('date')['pnl_rs'].sum()
    idx_cum = idx_daily.cumsum()
    idx_dd = (idx_cum - idx_cum.cummax()).min()
    
    idx_trades = len(idx_df)
    idx_wr = 100 * idx_df['won'].mean()
    idx_pnl = idx_df['pnl_rs'].sum()
    idx_max_win = idx_df['pnl_rs'].max()
    idx_max_loss = idx_df['pnl_rs'].min()
    
    print(f"Index: {idx}")
    print(f"  Trades: {idx_trades}")
    print(f"  Win Rate: {idx_wr:.2f}%")
    print(f"  Net PnL: Rs. {idx_pnl:+,.2f}")
    print(f"  Max Drawdown: Rs. {idx_dd:+,.2f}")
    print(f"  Max Profit in Single Trade: Rs. {idx_max_win:+,.2f}")
    print(f"  Max Loss in Single Trade: Rs. {idx_max_loss:+,.2f}")
    print("-" * 40)

print("\n=== ZERO_HERO PERFORMANCE ===")
zh_df = df[df['strategy'] == 'ZERO_HERO']
if len(zh_df) > 0:
    print(f"Trades: {len(zh_df)}")
    print(f"Win Rate: {100 * zh_df['won'].mean():.2f}%")
    print(f"Total PnL: Rs. {zh_df['pnl_rs'].sum():+,.2f}")
    print(f"Avg PnL/Trade: Rs. {zh_df['pnl_rs'].mean():+,.2f}")
    print(f"Max Profit Trade: Rs. {zh_df['pnl_rs'].max():+,.2f}")
    print(f"Max Loss Trade: Rs. {zh_df['pnl_rs'].min():+,.2f}")
else:
    print("No ZERO_HERO trades.")

print("\n=== GAMMA_BLAST PERFORMANCE ===")
gb_df = df[df['strategy'] == 'GAMMA_BLAST']
if len(gb_df) > 0:
    print(f"Trades: {len(gb_df)}")
    print(f"Win Rate: {100 * gb_df['won'].mean():.2f}%")
    print(f"Total PnL: Rs. {gb_df['pnl_rs'].sum():+,.2f}")
    print(f"Avg PnL/Trade: Rs. {gb_df['pnl_rs'].mean():+,.2f}")
    print(f"Max Profit Trade: Rs. {gb_df['pnl_rs'].max():+,.2f}")
    print(f"Max Loss Trade: Rs. {gb_df['pnl_rs'].min():+,.2f}")
else:
    print("No GAMMA_BLAST trades.")
