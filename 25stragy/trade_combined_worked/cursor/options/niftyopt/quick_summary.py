import pandas as pd
df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')

print('=== OPTION B + C COMBINED RESULTS ===\n')
print(f'Total Trades: {len(df)}')
print(f'Total PnL: ₹{df.pnl_rs.sum():,.0f}')
print(f'Win Rate: {df.won.sum()/len(df)*100:.1f}%')
print(f'Avg per trade: ₹{df.pnl_rs.mean():.0f}')
print(f'Lots avg: {df.lots.mean():.1f}\n')

# Daily metrics
daily = df.groupby('date')['pnl_rs'].sum().sort_index()
print('--- DAILY METRICS ---')
print(f'Best Day: ₹{daily.max():,.0f} ({daily.max()/500000*100:.1f}%)')
print(f'Worst Day: ₹{daily.min():,.0f} ({daily.min()/500000*100:.1f}%)')
print(f'Avg Day: ₹{daily.mean():.0f} ({daily.mean()/500000*100:.2f}%)')

# Max drawdown
running_max = daily.cummax()
drawdown = daily - running_max
max_dd = drawdown.min()
print(f'Max Drawdown: ₹{max_dd:,.0f} ({max_dd/500000*100:.1f}%)')

# Target achievement
days_8_15 = ((daily >= 40000) & (daily <= 75000)).sum()
days_above_15 = (daily > 75000).sum()
days_above_8 = (daily >= 40000).sum()
days_total = len(daily)

print(f'\n--- TARGET ₹40K-₹75K (8-15%) ---')
print(f'Days >= ₹40K: {days_above_8}/{days_total} ({days_above_8/days_total*100:.1f}%)')
print(f'Days ₹40K-₹75K: {days_8_15}/{days_total} ({days_8_15/days_total*100:.1f}%)')
print(f'Days > ₹75K: {days_above_15}/{days_total} ({days_above_15/days_total*100:.1f}%)')
print(f'Days >= ₹10K: {(daily >= 10000).sum()}/{days_total}')
print(f'Green Days: {(daily > 0).sum()}/{days_total} ({(daily > 0).sum()/days_total*100:.1f}%)')

# Per index
print('\n--- PER INDEX ---')
for idx, grp in df.groupby('index'):
    print(f'{idx:15s}: {len(grp)} trades, ₹{grp.pnl_rs.sum():>10,.0f}, avg ₹{grp.pnl_rs.mean():>6.0f}')

# Capital returns
print('\n--- CAPITAL RETURNS ---')
total = df.pnl_rs.sum()
print(f'Total Return: {total/500000*100:.1f}%')
print(f'Monthly (avg): ₹{daily.mean()*20:,.0f} ({daily.mean()*20/500000*100:.1f}%)')
