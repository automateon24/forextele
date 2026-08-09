import pandas as pd
import numpy as np

try:
    df = pd.read_csv('backtest_highres_signals.csv')
except Exception as e:
    print(f"Error reading CSV: {e}")
    exit()

if df.empty:
    print("CSV is empty.")
    exit()

df['win'] = (df['outcome'] == 'WIN').astype(int)

print("=== PATTERN ANALYSIS: 1:3 R:R TSL STRATEGIES ===\n")

print("1. PERFORMANCE BY HOUR (Top 5 Best & Worst)")
hourly = df.groupby('hour')['win'].agg(['count', 'mean']).reset_index()
hourly = hourly[hourly['count'] > 20] # Only statistically significant hours
hourly['mean'] = hourly['mean'] * 100
best_hours = hourly.sort_values('mean', ascending=False).head(5)
worst_hours = hourly.sort_values('mean', ascending=True).head(5)
print("Best Hours to Trade (High Win Rate):")
for _, r in best_hours.iterrows(): print(f" - Hour {int(r['hour'])}:00 UTC | Win Rate: {r['mean']:.1f}% | Trades: {int(r['count'])}")
print("Worst Hours to Trade (Avoid):")
for _, r in worst_hours.iterrows(): print(f" - Hour {int(r['hour'])}:00 UTC | Win Rate: {r['mean']:.1f}% | Trades: {int(r['count'])}")
print("")

print("2. PERFORMANCE BY TREND (ADX VALUE)")
df['adx_bin'] = pd.cut(df['adx_val'], bins=[0, 20, 30, 40, 100], labels=['Ranging (0-20)', 'Trending (20-30)', 'Strong Trend (30-40)', 'Extreme (40+)'])
adx_stats = df.groupby('adx_bin')['win'].agg(['count', 'mean']).dropna()
for bin_name, r in adx_stats.iterrows():
    print(f" - {bin_name}: Win Rate: {r['mean']*100:.1f}% | Trades: {int(r['count'])}")
print("")

print("3. PERFORMANCE BY MOMENTUM (RSI VALUE)")
df['rsi_bin'] = pd.cut(df['rsi_val'], bins=[0, 30, 45, 55, 70, 100], labels=['Oversold (0-30)', 'Weak (30-45)', 'Neutral (45-55)', 'Strong (55-70)', 'Overbought (70-100)'])
rsi_stats = df.groupby('rsi_bin')['win'].agg(['count', 'mean']).dropna()
for bin_name, r in rsi_stats.iterrows():
    print(f" - {bin_name}: Win Rate: {r['mean']*100:.1f}% | Trades: {int(r['count'])}")
print("")

print("4. STRATEGIES THAT CONSISTENTLY FULFILL 1:3 R:R (The Elite)")
strat_stats = df.groupby('strategy')['win'].agg(['count', 'mean'])
strat_stats = strat_stats[strat_stats['count'] > 30].sort_values('mean', ascending=False)
for strat, r in strat_stats.head(10).iterrows():
    print(f" - {strat}: Win Rate: {r['mean']*100:.1f}% | Trades: {int(r['count'])}")
