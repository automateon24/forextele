import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"
df = pd.read_csv(path)
print("Columns:", list(df.columns))
print("First row:")
print(df.iloc[0].to_dict())
