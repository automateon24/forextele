import pandas as pd
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

v3_path = r"C:\cursor\options\niftyopt\daily_data\v3_trades_20260625.csv"
v4_path = r"C:\cursor\options\niftyopt\daily_data\modular_trades_20260625.csv"
v15_path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"

def summarize_csv(path, name):
    if not os.path.exists(path):
        print(f"File {name} ({path}) does not exist.")
        return None
    try:
        df = pd.read_csv(path)
        print(f"=== {name} Trades Summary ===")
        print(f"Total rows: {len(df)}")
        print(df.head())
        return df
    except Exception as e:
        print(f"Error reading {name}: {e}")
        return None

v3_df = summarize_csv(v3_path, "V3")
v4_df = summarize_csv(v4_path, "V4/Modular")
v15_df = summarize_csv(v15_path, "V15")
