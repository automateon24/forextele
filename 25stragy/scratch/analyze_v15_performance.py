import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

v15_path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"
df = pd.read_csv(v15_path)

print("========================================")
print("V15 ENGINE - JUNE 25 PERFORMANCE REPORT")
print("========================================")

# overall stats
total_trades = len(df)
wins = df[df['pnl_rs'] > 0]
losses = df[df['pnl_rs'] <= 0]
win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
total_pnl = df['pnl_rs'].sum()

print(f"Total Trades: {total_trades}")
print(f"Wins: {len(wins)} | Losses: {len(losses)} | Win Rate: {win_rate:.1f}%")
print(f"Total Net P&L: Rs. {total_pnl:,.2f}")
print("-" * 50)

# index breakdown
print("\nINDEX PERFORMANCE BREAKDOWN:")
index_groups = df.groupby('index')
for name, group in index_groups:
    idx_total = len(group)
    idx_wins = len(group[group['pnl_rs'] > 0])
    idx_losses = len(group[group['pnl_rs'] <= 0])
    idx_win_rate = (idx_wins / idx_total) * 100
    idx_pnl = group['pnl_rs'].sum()
    print(f"  {name:<12} | Trades: {idx_total:<3} | W: {idx_wins:<2} | L: {idx_losses:<2} | WR: {idx_win_rate:.1f}% | P&L: Rs. {idx_pnl:+,.2f}")

# strategy breakdown
print("\nSTRATEGY PERFORMANCE BREAKDOWN:")
strat_groups = df.groupby('strategy')
for name, group in strat_groups:
    st_total = len(group)
    st_wins = len(group[group['pnl_rs'] > 0])
    st_losses = len(group[group['pnl_rs'] <= 0])
    st_win_rate = (st_wins / st_total) * 100
    st_pnl = group['pnl_rs'].sum()
    print(f"  {name:<20} | Trades: {st_total:<3} | W: {st_wins:<2} | L: {st_losses:<2} | WR: {st_win_rate:.1f}% | P&L: Rs. {st_pnl:+,.2f}")

# Exit Reason breakdown
print("\nEXIT REASONS:")
exit_groups = df.groupby('exit_reason')
for name, group in exit_groups:
    print(f"  {name:<15} | count: {len(group)} | P&L: Rs. {group['pnl_rs'].sum():+,.2f}")

print("\n--- ALL V15 TRADES FOR TODAY ---")
for idx, row in df.iterrows():
    print(f"{row['entry_time']} - {row['index']} - {row['strategy']} {row['direction']} | Entry: {row['entry_price']:.2f} | Exit: {row['exit_price']:.2f} | PnL: Rs. {row['pnl_rs']:+,.2f} | Reason: {row['exit_reason']}")
