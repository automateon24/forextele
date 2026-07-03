import pandas as pd

df = pd.read_csv("backtest_results/aggressive_100k_trades.csv")
zh = df[df['strategy'] == 'ZERO_HERO']
gb = df[df['strategy'] == 'GAMMA_BLAST']

print("=== ZERO_HERO PERFORMANCE ===")
print(f"Trades: {len(zh)}")
if len(zh) > 0:
    print(f"Win Rate: {len(zh[zh['pnl_rs'] > 0]) / len(zh) * 100:.1f}%")
    print(f"Total PnL: Rs. {zh['pnl_rs'].sum():,.2f}")
    print(f"Avg PnL/Trade: Rs. {zh['pnl_rs'].mean():,.2f}")
    print(f"Max Profit Trade: Rs. {zh['pnl_rs'].max():,.2f}")
    print(f"Max Loss Trade: Rs. {zh['pnl_rs'].min():,.2f}")
    print("\nTop 5 Winners:")
    print(zh.sort_values(by='pnl_rs', ascending=False)[['date', 'index', 'direction', 'entry_price', 'exit_price', 'exit_reason', 'pnl_rs']].head(5).to_string(index=False))
else:
    print("No trades triggered.")

print("\n=== GAMMA_BLAST PERFORMANCE ===")
print(f"Trades: {len(gb)}")
if len(gb) > 0:
    print(f"Win Rate: {len(gb[gb['pnl_rs'] > 0]) / len(gb) * 100:.1f}%")
    print(f"Total PnL: Rs. {gb['pnl_rs'].sum():,.2f}")
    print(f"Avg PnL/Trade: Rs. {gb['pnl_rs'].mean():,.2f}")
    print(f"Max Profit Trade: Rs. {gb['pnl_rs'].max():,.2f}")
    print(f"Max Loss Trade: Rs. {gb['pnl_rs'].min():,.2f}")
    print("\nTop 5 Winners:")
    print(gb.sort_values(by='pnl_rs', ascending=False)[['date', 'index', 'direction', 'entry_price', 'exit_price', 'exit_reason', 'pnl_rs']].head(5).to_string(index=False))
else:
    print("No trades triggered.")

print("\n=== OVERALL COMBINED PORTFOLIO ===")
print(f"Total Trades: {len(df)}")
print(f"Combined Win Rate: {len(df[df['pnl_rs'] > 0]) / len(df) * 100:.1f}%")
print(f"Total PnL: Rs. {df['pnl_rs'].sum():,.2f}")
