import pandas as pd
import numpy as np

csv_path = r"C:\25stragy\backtest_results\aggressive_100k_trades.csv"
df = pd.read_csv(csv_path)

# Calculate metrics per strategy
stats = []
grouped = df.groupby('strategy')

for name, group in grouped:
    total_trades = len(group)
    wins = group['won'].sum()
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0.0
    net_pnl = group['pnl_rs'].sum()
    avg_pnl = group['pnl_rs'].mean()
    max_win = group['pnl_rs'].max()
    max_loss = group['pnl_rs'].min()
    
    stats.append({
        'Strategy': name,
        'Trades': total_trades,
        'Win Rate (%)': win_rate,
        'Net PnL (Rs.)': net_pnl,
        'Avg PnL (Rs.)': avg_pnl,
        'Max Win (Rs.)': max_win,
        'Max Loss (Rs.)': max_loss
    })

# Convert to DataFrame and sort by Net PnL descending
stats_df = pd.DataFrame(stats).sort_values(by='Net PnL (Rs.)', ascending=False)

print(stats_df.to_markdown(index=False, floatfmt=".2f"))
