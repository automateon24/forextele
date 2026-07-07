import MetaTrader5 as mt5
from datetime import datetime
import pandas as pd

if not mt5.initialize():
    print("initialize() failed")
    mt5.shutdown()
    exit()

today = datetime.now()
from_date = datetime(today.year, today.month, today.day)
to_date = datetime(today.year, today.month, today.day, 23, 59, 59)

history_deals = mt5.history_deals_get(from_date, to_date)
if history_deals:
    df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
    print("Recent MT5 Deals:")
    for _, row in df.tail(10).iterrows():
        action = "BUY" if row['type'] == mt5.DEAL_TYPE_BUY else "SELL"
        print(f"[{row['symbol']}] {action} | Volume: {row['volume']} | Comment: {row['comment']}")
else:
    print("No deals found today.")

mt5.shutdown()
