import pandas as pd
import os

csv_path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"

if not os.path.exists(csv_path):
    print("CSV file does not exist!")
    sys.exit(1)

df = pd.read_csv(csv_path)
print("Columns in CSV:", df.columns.tolist())
print(f"Total rows: {len(df)}")

# Filter for today: 2026-06-25
today_df = df[df['entry_time'].str.startswith('2026-06-25')]
print(f"Trades for June 25: {len(today_df)}")

# Print all trades for today
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', 1000)

print(today_df[['index', 'strategy', 'direction', 'strike', 'entry_time', 'exit_time', 'status', 'entry_price', 'exit_price', 'pnl_rs']])
