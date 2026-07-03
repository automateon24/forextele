import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

v15_path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"
df = pd.read_csv(v15_path)

print("=== V15 Trades Details (Lot Sizes & Premiums) ===")
cols = ['entry_time', 'index', 'strategy', 'direction', 'lots', 'entry_price', 'exit_price', 'pnl_rs', 'exit_reason']
print(df[cols].to_string())
