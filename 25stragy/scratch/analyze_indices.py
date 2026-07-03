import pandas as pd
import os

csv_path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"
if os.path.exists(csv_path):
    df = pd.read_csv(csv_path)
    print("=== Cumulative Performance by Index ===")
    summary = df.groupby('index').agg(
        trades=('pnl_rs', 'count'),
        total_pnl=('pnl_rs', 'sum'),
        wins=('pnl_rs', lambda x: (x > 0).sum()),
        losses=('pnl_rs', lambda x: (x <= 0).sum())
    )
    summary['win_rate'] = (summary['wins'] / summary['trades']) * 100
    print(summary)
else:
    print("No trade file found!")
