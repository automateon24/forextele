import pandas as pd
df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')
print(f'Trades: {len(df)}')
print(f'Lots: {df.lots.mean():.1f} (unique: {sorted(df.lots.unique())})')
print(f'Indices: {df["index"].value_counts().to_dict()}')
print(f'PnL: ₹{df.pnl_rs.sum():,.0f}')
daily = df.groupby('date')['pnl_rs'].sum()
print(f'Best Day: ₹{daily.max():,.0f} ({daily.max()/500000*100:.1f}%)')
print(f'Days >= ₹40K: {(daily >= 40000).sum()}/{len(daily)}')
