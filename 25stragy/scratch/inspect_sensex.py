import pandas as pd

csv_path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"
df = pd.read_csv(csv_path)

sensex_trade = df[(df['index'] == 'SENSEX') & (df['entry_time'].str.startswith('2026-06-25'))]
print(sensex_trade.to_dict(orient='records')[0])
