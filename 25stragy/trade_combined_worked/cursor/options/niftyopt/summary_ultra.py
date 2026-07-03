import pandas as pd
df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')

print('=== ULTRA-SCALE AGGRESSIVE (8-12 lots) ===\n')
print(f"Target: ₹40,000-₹75,000/day (8-15% of ₹5L capital)\n")

print(f"Total Trades: {len(df)}")
print(f"Total PnL: ₹{df.pnl_rs.sum():,.0f}")
print(f"Win Rate: {df.won.sum()/len(df)*100:.1f}%")
print(f"Avg per trade: ₹{df.pnl_rs.mean():.0f}")
print(f"Lots avg: {df.lots.mean():.1f}")
print()

# Daily analysis with drawdown
daily = df.groupby('date')['pnl_rs'].sum().sort_index()
print('--- DAILY METRICS ---')
print(f"Best Day: ₹{daily.max():,.0f} ({daily.max()/500000*100:.1f}%)")
print(f"Avg Day: ₹{daily.mean():.0f} ({daily.mean()/500000*100:.2f}%)")
print(f"Worst Day: ₹{daily.min():,.0f} ({daily.min()/500000*100:.1f}%)")

# Max drawdown calculation (running from peak)
running_max = daily.cummax()
drawdown = daily - running_max
max_dd = drawdown.min()
max_dd_day = drawdown.idxmin()
print(f"Max Drawdown: ₹{max_dd:,.0f} ({max_dd/500000*100:.1f}%) on {max_dd_day}")

# Days in target range
days_8_15 = ((daily >= 40000) & (daily <= 75000)).sum()
days_above_15 = (daily > 75000).sum()
days_above_8 = (daily >= 40000).sum()
days_total = len(daily)

print(f"\nDays >= ₹40K (8%): {days_above_8}/{days_total} ({days_above_8/days_total*100:.1f}%)")
print(f"Days ₹40K-₹75K (8-15%): {days_8_15}/{days_total} ({days_8_15/days_total*100:.1f}%)")
print(f"Days > ₹75K (>15%): {days_above_15}/{days_total} ({days_above_15/days_total*100:.1f}%)")
print(f"Days >= ₹10K (2%): {(daily >= 10000).sum()}/{days_total}")
print(f"Days >= ₹5K (1%): {(daily >= 5000).sum()}/{days_total}")
print(f"Green Days: {(daily > 0).sum()}/{days_total} ({(daily > 0).sum()/days_total*100:.1f}%)")
print()

# Per index
print('--- PER INDEX ---')
idx_stats = df.groupby('index')['pnl_rs'].agg(['count', 'sum', 'mean']).round(0)
idx_stats['per_trade'] = (df.groupby('index')['pnl_rs'].mean()).round(0)
for idx, row in idx_stats.iterrows():
    print(f"{idx:15s}: {int(row['count'])} trades, ₹{int(row['sum']):>9,}, avg ₹{int(row['mean']):>7}")

print()

# Capital returns
capital = 500000
total = df.pnl_rs.sum()
print('--- CAPITAL RETURNS ---')
print(f"Total Return: {total/capital*100:.1f}%")
print(f"Daily Avg: {daily.mean()/capital*100:.2f}%")
print(f"Monthly (avg): ₹{daily.mean()*20:,.0f} ({daily.mean()*20/capital*100:.1f}%)")

# Worst days table
print('\n--- WORST 5 DAYS (Drawdown) ---')
worst = daily.sort_values().head(5)
for dt, pnl in worst.items():
    print(f"{str(dt)[:10]}: ₹{pnl:>+8,.0f} ({pnl/capital*100:>5.1f}%)")

# Best days table  
print('\n--- BEST 5 DAYS ---')
best = daily.sort_values(ascending=False).head(5)
for dt, pnl in best.items():
    print(f"{str(dt)[:10]}: ₹{pnl:>+8,.0f} ({pnl/capital*100:>5.1f}%)")
