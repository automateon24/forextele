import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"
try:
    df = pd.read_csv(path)
    print("Trade log columns:", df.columns.tolist())
    print("Total rows:", len(df))
    # Filter for June 25
    df_june25 = df[df['entry_time'].astype(str).str.contains('2026-06-25')]
    print("\nTrades on June 25:")
    print(df_june25[['entry_time', 'index', 'strategy', 'direction', 'entry_price', 'exit_price', 'pnl_rs', 'option_name', 'option_security_id']])
except Exception as e:
    print("Error reading trades CSV:", e)
