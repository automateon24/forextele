import pandas as pd
import json

csv_path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"
df = pd.read_csv(csv_path)

large_losses = df[df['pnl_rs'] < -5000]
print("=== Large Loss Details ===")
for r in large_losses.to_dict(orient='records'):
    print(r)
