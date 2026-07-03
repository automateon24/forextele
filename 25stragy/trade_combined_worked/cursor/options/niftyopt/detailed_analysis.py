import pandas as pd
import numpy as np
import sys

sys.path.insert(0, r'c:\cursor\options\niftyopt')

print('='*70)
print('DETAILED ANALYSIS: 5-10% DAILY TARGET | LOOSER TSL (3%/8%/60%)')
print('='*70)

df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')
df['date'] = pd.to_datetime(df['date'])

print(f'\n=== OVERALL METRICS ===')
print(f'Total Trades: {len(df)}')
print(f'Total PnL: Rs.{df.pnl_rs.sum():,.0f}')
print(f'Win Rate: {df.won.sum()/len(df)*100:.1f}%')
print(f'Avg PnL/Trade: Rs.{df.pnl_rs.mean():.0f}')
print(f'Median PnL/Trade: Rs.{df.pnl_rs.median():.0f}')
print(f'Lots/Trade: {df.lots.mean():.1f}')

# Per-index detailed analysis
print(f'\n=== PER-INDEX DETAILED BREAKDOWN ===')
for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
    idx_df = df[df['index'] == idx]
    if len(idx_df) == 0:
        continue
    
    idx_daily = idx_df.groupby('date')['pnl_rs'].sum()
    wins = idx_df.won.sum()
    losses = len(idx_df) - wins
    
    print(f'\n{idx}:')
    print(f'  Trades: {len(idx_df)} | Win: {wins} | Loss: {losses} | Win%: {wins/len(idx_df)*100:.1f}%')
    print(f'  Total PnL: Rs.{idx_df.pnl_rs.sum():,.0f}')
    print(f'  Avg/Trade: Rs.{idx_df.pnl_rs.mean():.0f}')
    print(f'  Best Trade: Rs.{idx_df.pnl_rs.max():,.0f}')
    print(f'  Worst Trade: Rs.{idx_df.pnl_rs.min():,.0f}')
    print(f'  Best Day: Rs.{idx_daily.max():,.0f} ({idx_daily.max()/500000*100:.1f}%)')
    print(f'  Worst Day: Rs.{idx_daily.min():,.0f} ({idx_daily.min()/500000*100:.1f}%)')
    print(f'  Avg Day: Rs.{idx_daily.mean():.0f}')
    
    # Drawdown for this index
    idx_running_max = idx_daily.cummax()
    idx_drawdown = idx_daily - idx_running_max
    max_dd = idx_drawdown.min()
    print(f'  Max Drawdown: Rs.{max_dd:,.0f} ({max_dd/500000*100:.1f}%)')

# Daily combined analysis
print(f'\n=== COMBINED DAILY ANALYSIS (All Indices) ===')
daily = df.groupby('date')['pnl_rs'].sum().sort_index()
print(f'Trading Days: {len(daily)}')
print(f'Best Day: Rs.{daily.max():,.0f} ({daily.max()/500000*100:.1f}%)')
print(f'Worst Day: Rs.{daily.min():,.0f} ({daily.min()/500000*100:.1f}%)')
print(f'Avg Day: Rs.{daily.mean():.0f} ({daily.mean()/500000*100:.2f}%)')
print(f'Median Day: Rs.{daily.median():.0f}')

# Drawdown analysis
running_max = daily.cummax()
drawdown = daily - running_max
max_dd = drawdown.min()
max_dd_pct = max_dd / 500000 * 100

print(f'\n=== DRAWDOWN ANALYSIS ===')
print(f'Max Drawdown: Rs.{max_dd:,.0f} ({max_dd_pct:.1f}%)')
print(f'Drawdown Days: {(drawdown < 0).sum()}/{len(daily)}')

# Target achievement
print(f'\n=== TARGET ACHIEVEMENT (5-10% Daily = Rs.25K-50K) ===')
days_5pct = (daily >= 25000).sum()
days_10pct = (daily >= 50000).sum()
days_15pct = (daily >= 75000).sum()
print(f'Days >= Rs.25K (5%):  {days_5pct}/{len(daily)} ({days_5pct/len(daily)*100:.1f}%)')
print(f'Days >= Rs.50K (10%): {days_10pct}/{len(daily)} ({days_10pct/len(daily)*100:.1f}%)')
print(f'Days >= Rs.75K (15%): {days_15pct}/{len(daily)} ({days_15pct/len(daily)*100:.1f}%)')

# Day distribution
print(f'\n=== DAY DISTRIBUTION ===')
print(f'Loss Days (<0):     {(daily < 0).sum()}')
print(f'Rs.0-10K:          {((daily >= 0) & (daily < 10000)).sum()}')
print(f'Rs.10K-25K:        {((daily >= 10000) & (daily < 25000)).sum()}')
print(f'Rs.25K-50K (5-10%): {((daily >= 25000) & (daily < 50000)).sum()}')
print(f'Rs.50K-75K:        {((daily >= 50000) & (daily < 75000)).sum()}')
print(f'>= Rs.75K:          {(daily >= 75000).sum()}')

# Exit type analysis
print(f'\n=== EXIT TYPE ANALYSIS ===')
for exit_type in df['exit'].unique():
    exit_df = df[df['exit'] == exit_type]
    print(f'{exit_type:12s}: {len(exit_df):3d} trades | Avg: Rs.{exit_df.pnl_rs.mean():>7.0f} | Win%: {exit_df.won.sum()/len(exit_df)*100:.0f}%')

# Top strategies
print(f'\n=== TOP 10 STRATEGIES BY PnL ===')
strat_pnl = df.groupby('strategy')['pnl_rs'].sum().sort_values(ascending=False)
for i, (strat, pnl) in enumerate(strat_pnl.head(10).items(), 1):
    strat_df = df[df['strategy'] == strat]
    print(f'{i:2d}. {strat:25s}: Rs.{pnl:>8,.0f} ({len(strat_df):3d} trades)')

print(f'\n' + '='*70)
print('SUMMARY: Looser TSL (3%/8%/60%) with 2 lots targeting 5-10% daily')
print('='*70)
