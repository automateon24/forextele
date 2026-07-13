import pandas as pd
import numpy as np

# Load backtest results
df = pd.read_csv("backtest_1week_results.csv")
df['time'] = pd.to_datetime(df['time'])

# We need to approximate the exit time for each trade in the backtest.
# Let's assume standard time frame for each strategy:
# Strategies are either M5 (mean reversion, rsi, morning breakout, momentum, asian range, scalping, pip blast) 
# or M15 (trend, breakout, london breakout, etc.) or H1 (day high/low traditional, order block, ultimate day high/low, institutional support).
# Since a trade expires in 48 bars, max duration is:
# - M5 strategies: 48 * 5 = 240 mins (4 hours)
# - M15 strategies: 48 * 15 = 720 mins (12 hours)
# - H1 strategies: 48 * 60 = 2880 mins (48 hours)
# Let's assign an exit timestamp based on outcome and average duration:
# - WIN/LOSS: typically hits mid-way, say 12 bars on average.
# - EXPIRED: 48 bars.

def estimate_duration_mins(row):
    sn = row['strategy']
    is_m5 = sn in ("MEAN_REVERSION", "RSI_REVERSAL", "NY_OPEN_REVERSAL", "ASIAN_RANGE_SCALP", "BOLLINGER_SQUEEZE")
    is_m1 = sn in ("SCALPING", "PIP_BLAST", "MOMENTUM_BURST")
    # Determine base period in minutes
    if is_m1:
        base = 1
    elif is_m5:
        base = 5
    else:
        base = 15  # default to 15 mins
    
    bars = 12 if row['outcome'] in ('WIN', 'LOSS') else 48
    return bars * base

df['duration_mins'] = df.apply(estimate_duration_mins, axis=1)
df['exit_time'] = df['time'] + pd.to_timedelta(df['duration_mins'], unit='m')

# Generate timeline of events
events = []
for idx, row in df.iterrows():
    events.append((row['time'], 1, row['symbol'], row['strategy']))
    events.append((row['exit_time'], -1, row['symbol'], row['strategy']))

# Sort events by time
events.sort(key=lambda x: x[0])

# Calculate rolling concurrency
max_concurrent = 0
current_concurrent = 0
concurrency_by_symbol = {}
max_concurrent_by_symbol = {}

# Margin requirements per trade for 0.10 lots under 1:500 leverage:
# Forex: ~$20 margin, Gold: ~$46 margin, Silver: ~$30 margin, BTC: ~$12 margin, ETH: ~$1 margin.
margin_map = {
    "EURUSD": 20.0,
    "GBPUSD": 20.0,
    "USDJPY": 20.0,
    "AUDUSD": 20.0,
    "GOLD": 46.0,
    "SILVER": 30.0,
    "BTCUSD": 12.0,
    "ETHUSD": 1.0
}

current_margin = 0.0
max_margin = 0.0

for t, val, sym, strat in events:
    current_concurrent += val
    if current_concurrent > max_concurrent:
        max_concurrent = current_concurrent
    
    concurrency_by_symbol[sym] = concurrency_by_symbol.get(sym, 0) + val
    if concurrency_by_symbol[sym] > max_concurrent_by_symbol.get(sym, 0):
        max_concurrent_by_symbol[sym] = concurrency_by_symbol[sym]
    
    margin_cost = margin_map.get(sym, 20.0)
    current_margin += val * margin_cost
    if current_margin > max_margin:
        max_margin = current_margin

print(f"Max Concurrent Open Trades across all symbols: {max_concurrent}")
print(f"Max Margin Required (Capital Utilized): ${max_margin:.2f}")
print("Max Concurrent Trades per Symbol:")
for sym, count in max_concurrent_by_symbol.items():
    print(f"  {sym}: {count} trades (Max Margin: ${count * margin_map.get(sym, 20.0):.2f})")
