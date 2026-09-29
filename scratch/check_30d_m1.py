import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta

if not mt5.initialize():
    print("Failed to initialize MT5")
    exit()

now = datetime.now(timezone.utc)
from_date = now - timedelta(days=32)

for sym in ["GOLD", "BTCUSD"]:
    rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1, from_date, now)
    if rates is not None and len(rates) > 0:
        first_time = datetime.fromtimestamp(rates[0]['time'], tz=timezone.utc)
        last_time = datetime.fromtimestamp(rates[-1]['time'], tz=timezone.utc)
        print(f"{sym}: {len(rates)} M1 candles from {first_time} to {last_time}")
    else:
        print(f"{sym}: No M1 candles returned")

mt5.shutdown()
