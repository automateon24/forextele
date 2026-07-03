import pandas as pd
try:
    df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')
    print(f'Trades: {len(df)} | Lots avg: {df.lots.mean():.1f} | Total PnL: ₹{df.pnl_rs.sum():,.0f}')
    daily = df.groupby('date')['pnl_rs'].sum()
    print(f'Days: {len(daily)} | Best: ₹{daily.max():,.0f} | Avg: ₹{daily.mean():.0f}')
    print(f'Indices: {df["index"].nunique()} | {list(df["index"].unique())}')
    print(f'Lots values: {sorted(df.lots.unique())}')
except Exception as e:
    print(f'Error: {e}')
