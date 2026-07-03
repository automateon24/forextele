import pandas as pd

csv_path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"
df = pd.read_csv(csv_path)

large_losses = df[df['pnl_rs'] < -5000]
print("=== Trades with Losses > Rs. 5,000 ===")
print(large_losses[['index', 'strategy', 'direction', 'strike', 'lots', 'entry_price', 'exit_price', 'exit_reason', 'pnl_rs', 'entry_time', 'exit_time']])
