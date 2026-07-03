import pandas as pd
df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')

print('=== 15% TARGET OPTIMIZED | 2 LOTS | ALL INDICES ===')
print('Looser TSL (6% trail), Lower conf (0.52/0.55), More trades (15/dir)\n')
print(f"Target: ₹75,000/day (15% of ₹5L capital)")
print(f"Config: 2 lots, TSL(4%/6%), Target 50%, 0.52/0.55 conf, 15 trades/dir\n")

print(f"Total Trades: {len(df)}")
print(f"Total PnL: ₹{df.pnl_rs.sum():,.0f}")
print(f"Win Rate: {df.won.sum()/len(df)*100:.1f}%")
print(f"Avg per trade: ₹{df.pnl_rs.mean():.0f}")
print(f"Lots avg: {df.lots.mean():.1f}")
print()

# Daily analysis with drawdown
daily = df.groupby('date')['pnl_rs'].sum().sort_index()
print('--- DAILY P&L METRICS ---')
print(f"Best Day: ₹{daily.max():,.0f} ({daily.max()/500000*100:.1f}%)")
print(f"Avg Day: ₹{daily.mean():.0f} ({daily.mean()/500000*100:.2f}%)")
print(f"Median Day: ₹{daily.median():.0f}")
print(f"Worst Day: ₹{daily.min():,.0f} ({daily.min()/500000*100:.1f}%)")

# Max drawdown calculation (running from peak)
running_max = daily.cummax()
drawdown = daily - running_max
max_dd = drawdown.min()
max_dd_date = drawdown.idxmin()
max_dd_peak = running_max[max_dd_date]
print(f"\nMax Drawdown: ₹{max_dd:,.0f} ({max_dd/500000*100:.1f}%)")
print(f"  Peak before DD: ₹{max_dd_peak:,.0f} on {max_dd_date}")

# Recovery days
recovery_days = 0
for i in range(len(drawdown)):
    if drawdown.iloc[i] == max_dd:
        for j in range(i+1, len(drawdown)):
            if drawdown.iloc[j] == 0:
                recovery_days = j - i
                break
        break
print(f"  Recovery: {recovery_days} trading days")

# Days in target range
days_8_15 = ((daily >= 40000) & (daily <= 75000)).sum()
days_above_15 = (daily > 75000).sum()
days_above_8 = (daily >= 40000).sum()
days_total = len(daily)

print(f"\n--- TARGET ACHIEVEMENT ---")
print(f"Days >= ₹40K (8%): {days_above_8}/{days_total} ({days_above_8/days_total*100:.1f}%)")
print(f"Days ₹40K-₹75K (8-15%): {days_8_15}/{days_total} ({days_8_15/days_total*100:.1f}%)")
print(f"Days > ₹75K (>15%): {days_above_15}/{days_total} ({days_above_15/days_total*100:.1f}%)")
print(f"Days >= ₹10K (2%): {(daily >= 10000).sum()}/{days_total}")
print(f"Days >= ₹5K (1%): {(daily >= 5000).sum()}/{days_total}")
print(f"Green Days: {(daily > 0).sum()}/{days_total} ({(daily > 0).sum()/days_total*100:.1f}%)")
print(f"Red Days: {(daily < 0).sum()}/{days_total}")

# Per index
print('\n--- PER INDEX (1 Lot) ---')
idx_stats = df.groupby('index').agg({
    'pnl_rs': ['count', 'sum', 'mean'],
    'won': 'sum'
}).round(0)
idx_stats.columns = ['trades', 'total', 'avg_trade', 'wins']
for idx, row in idx_stats.iterrows():
    wr = row['wins']/row['trades']*100
    print(f"{idx:15s}: {int(row['trades'])} trades, ₹{int(row['total']):>10,}, avg ₹{int(row['avg_trade']):>6}, WR {wr:.0f}%")

print()

# Capital returns
capital = 500000
total = df.pnl_rs.sum()
print('--- CAPITAL RETURNS ---')
print(f"Total Return: {total/capital*100:.1f}%")
print(f"Daily Avg: {daily.mean()/capital*100:.2f}%")
print(f"Monthly (20 days): ₹{daily.mean()*20:,.0f} ({daily.mean()*20/capital*100:.1f}%)")
print(f"Annual (250 days): ₹{daily.mean()*250:,.0f} ({daily.mean()*250/capital*100:.0f}%)")

# Worst days table
print('\n--- WORST 5 DAYS (Drawdown Risk) ---')
worst = daily.sort_values().head(5)
for dt, pnl in worst.items():
    print(f"{str(dt)[:10]}: ₹{pnl:>+8,.0f} ({pnl/capital*100:>5.1f}%)")

# Best days table  
print('\n--- BEST 10 DAYS (Target Days) ---')
best = daily.sort_values(ascending=False).head(10)
for dt, pnl in best.items():
    print(f"{str(dt)[:10]}: ₹{pnl:>+8,.0f} ({pnl/capital*100:>5.1f}%)")

# Monthly
print('\n--- MONTHLY BREAKDOWN ---')
df['month'] = pd.to_datetime(df['date']).dt.to_period('M')
monthly = df.groupby('month')['pnl_rs'].sum()
for m, v in monthly.items():
    pct = v / capital * 100
    bar = '#' * min(int(abs(v)/2000), 40)
    print(f"{m}: ₹{v:>+9,.0f} ({pct:>+5.1f}%) {bar}")
