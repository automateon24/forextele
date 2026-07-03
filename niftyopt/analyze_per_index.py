import pandas as pd
df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')

print("=== PER INDEX DEEP ANALYSIS ===\n")

for idx in ['NIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
    idx_df = df[df['index'] == idx]
    if len(idx_df) == 0:
        continue
    
    print(f"\n{idx}:")
    print(f"  Trades: {len(idx_df)}")
    print(f"  Total PnL: ₹{idx_df.pnl_rs.sum():,.0f}")
    print(f"  Per Trade: ₹{idx_df.pnl_rs.mean():.0f}")
    print(f"  Win Rate: {idx_df.won.sum()/len(idx_df)*100:.1f}%")
    print(f"  Lots avg: {idx_df.lots.mean():.1f}")
    print(f"  PnL pts avg: {idx_df.pnl_pts.mean():.2f}")
    
    # Per strategy
    print(f"  Per Strategy:")
    strat_stats = idx_df.groupby('strategy')['pnl_rs'].agg(['count', 'sum', 'mean']).sort_values('sum', ascending=False)
    for strat, row in strat_stats.head(5).iterrows():
        print(f"    {strat:20s}: {int(row['count'])} trades, ₹{int(row['sum']):>8,}, avg ₹{int(row['mean']):>6}")
    
    # Exit reasons
    print(f"  Exit Breakdown:")
    exit_stats = idx_df.groupby('exit_reason')['pnl_rs'].agg(['count', 'sum', 'mean'])
    for ex, row in exit_stats.iterrows():
        print(f"    {ex:10s}: {int(row['count'])} trades, ₹{int(row['sum']):>8,}, avg ₹{int(row['mean']):>6}")

print("\n\n=== KEY INSIGHTS ===")
print("NIFTY avg per trade is 5-10x higher than other indices!")
print("This suggests either:")
print("1. Lot size calculation wrong for other indices")
print("2. Premium scaling not applied correctly")
print("3. Entry/exit prices different (slippage model)")
print("4. Strategy profiles too conservative for non-NIFTY")
