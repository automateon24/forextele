import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import pandas as pd

if not mt5.initialize():
    print("MT5 init failed")
    exit(1)

now = datetime.now(timezone.utc)
start = datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc)

symbols = ["GOLD", "BTCUSD", "GBPNZD", "EURUSD", "GBPUSD", "USDJPY", "US30Cash"]
for s in symbols:
    rates = mt5.copy_rates_range(s, mt5.TIMEFRAME_M1, start, now)
    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)
        print(f"Symbol: {s:<10} | Bars: {len(df):>5} | Open: {df['open'].iloc[0]} | High: {df['high'].max()} | Low: {df['low'].min()} | Last: {df['close'].iloc[-1]}")
    else:
        print(f"Symbol: {s:<10} | No M1 data!")
