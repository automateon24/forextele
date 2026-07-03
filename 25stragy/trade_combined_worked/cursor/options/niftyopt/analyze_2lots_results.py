import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')
df['date'] = pd.to_datetime(df['date'])

print('='*70)
print('2 LOTS | ALL 5 INDICES | ALL 24 STRATEGIES ANALYSIS')
print('='*70)

# Basic metrics
print('\n--- OVERALL METRICS ---')
print(f'Total Trades: {len(df)}')
print(f'Total PnL: ₹{df.pnl_rs.sum():,.0f}')
print(f'Win Rate: {df.won.sum()/len(df)*100:.1f}%')
print(f'Avg PnL/Trade: ₹{df.pnl_rs.mean():.0f}')
print(f'Median PnL/Trade: ₹{df.pnl_rs.median():.0f}')
print(f'Lots: {df.lots.mean():.1f}')

# Daily analysis
daily = df.groupby('date')['pnl_rs'].sum().sort_index()
print('\n--- DAILY METRICS ---')
print(f'Trading Days: {len(daily)}')
print(f'Best Day: ₹{daily.max():,.0f} ({daily.max()/500000*100:.1f}%)')
print(f'Worst Day: ₹{daily.min():,.0f} ({daily.min()/500000*100:.1f}%)')
print(f'Avg Day: ₹{daily.mean():.0f} ({daily.mean()/500000*100:.2f}%)')
print(f'Median Day: ₹{daily.median():.0f}')

# Target achievement
days_8pct = (daily >= 40000).sum()
days_15pct = (daily >= 75000).sum()
print(f'\n--- TARGET ₹40K-₹75K (8-15%) ---')
print(f'Days ≥ ₹40K: {days_8pct}/{len(daily)} ({days_8pct/len(daily)*100:.1f}%)')
print(f'Days ≥ ₹75K: {days_15pct}/{len(daily)} ({days_15pct/len(daily)*100:.1f}%)')

# Drawdown
running_max = daily.cummax()
drawdown = daily - running_max
max_dd = drawdown.min()
print(f'\n--- DRAWDOWN ---')
print(f'Max Drawdown: ₹{max_dd:,.0f} ({max_dd/500000*100:.1f}%)')

# Per-index analysis
print('\n--- PER-INDEX BREAKDOWN ---')
for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
    idx_df = df[df['index'] == idx]
    if len(idx_df) > 0:
        idx_daily = idx_df.groupby('date')['pnl_rs'].sum()
        print(f'{idx:12s}: {len(idx_df):3d} trades | PnL: ₹{idx_df.pnl_rs.sum():>8,.0f} | '
              f'Avg: ₹{idx_df.pnl_rs.mean():>6.0f} | Win: {idx_df.won.sum()/len(idx_df)*100:.0f}% | '
              f'Best Day: ₹{idx_daily.max():>7,.0f}')

# Exit analysis
print('\n--- EXIT TYPE ANALYSIS ---')
for exit_type in df['exit'].unique():
    exit_df = df[df['exit'] == exit_type]
    print(f'{exit_type:10s}: {len(exit_df):3d} trades | Avg: ₹{exit_df.pnl_rs.mean():>6.0f} | '
          f'Win: {exit_df.won.sum()/len(exit_df)*100:.0f}%')

# Strategy analysis
print('\n--- TOP STRATEGIES BY PnL ---')
strat_pnl = df.groupby('strategy')['pnl_rs'].sum().sort_values(ascending=False)
for strat, pnl in strat_pnl.head(10).items():
    strat_df = df[df['strategy'] == strat]
    print(f'{strat:25s}: ₹{pnl:>8,.0f} ({len(strat_df):2d} trades, ₹{pnl/len(strat_df):.0f}/trade)')

# Gap to target analysis
print('\n--- GAP TO 15% TARGET (₹75,000/day) ---')
avg_daily = daily.mean()
gap_to_target = 75000 - avg_daily
print(f'Current Avg: ₹{avg_daily:.0f}/day')
print(f'Target: ₹75,000/day')
print(f'Gap: ₹{gap_to_target:,.0f}/day ({gap_to_target/75000*100:.1f}% short)')
print(f'\nTo reach ₹75K/day, need:')
print(f'  - {75000/avg_daily:.1f}x more trades/day, OR')
print(f'  - ₹{75000/daily.mean()*avg_daily:.0f} avg profit/trade (current: ₹{df.pnl_rs.mean():.0f}), OR')
print(f'  - {75000/avg_daily:.1f}x more lots (would be {2*75000/avg_daily:.0f} lots)')

# Days analysis
print('\n--- DAY DISTRIBUTION ---')
print(f'₹0-10K: {((daily >= 0) & (daily < 10000)).sum()} days')
print(f'₹10-25K: {((daily >= 10000) & (daily < 25000)).sum()} days')
print(f'₹25-50K: {((daily >= 25000) & (daily < 50000)).sum()} days')
print(f'₹50-75K: {((daily >= 50000) & (daily < 75000)).sum()} days')
print(f'≥₹75K: {(daily >= 75000).sum()} days')
