import pandas as pd

csv_path = r"C:\25stragy\backtest_results\aggressive_100k_trades.csv"
df = pd.read_csv(csv_path)

print("=== STRATEGY PERFORMANCE BREAKDOWN ===")
strat_summary = []
for strat in df['strategy'].unique():
    sub = df[df['strategy'] == strat]
    trades = len(sub)
    win_rate = 100 * sub['won'].mean()
    total_pnl = sub['pnl_rs'].sum()
    avg_pnl = sub['pnl_rs'].mean()
    
    strat_summary.append({
        'Strategy': strat,
        'Trades': trades,
        'Win Rate (%)': win_rate,
        'Total PnL (Rs.)': total_pnl,
        'Avg PnL/Trade (Rs.)': avg_pnl
    })

summary_df = pd.DataFrame(strat_summary).sort_values(by='Total PnL (Rs.)', ascending=False)
print(summary_df.to_string(index=False))
