import pandas as pd

df = pd.read_csv("backtest_results/aggressive_100k_trades.csv")
# Filter for ZERO_HERO and GAMMA_BLAST
zh_gb = df[df['strategy'].isin(['ZERO_HERO', 'GAMMA_BLAST'])].copy()

print(f"Total ZERO_HERO & GAMMA_BLAST Trades: {len(zh_gb)}")
print(zh_gb[['date', 'index', 'strategy', 'direction', 'entry_time', 'entry_price', 'exit_price', 'exit_reason', 'pnl_pts', 'pnl_rs']].to_string())
