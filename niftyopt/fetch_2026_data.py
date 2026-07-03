"""
Fetch NIFTY options 1-min data for manual trade dates from Dhan API
and replay the ULTIMATE_DAY_HIGH_LOW strategy against them.
"""
import sys, os, time
sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd
from datetime import datetime, date
from dhanhq import dhanhq

# Load token
import json
token_file = r'c:\cursor\options\niftyopt\config\dhan_tokens.json'
with open(token_file) as f:
    token = json.load(f)['access_token']

dhan = dhanhq("1101936133", token)

# Manual trade dates to fetch
TRADE_DATES = [
    '2026-04-30', '2026-05-04', '2026-05-05', '2026-05-06',
    '2026-05-07', '2026-05-08', '2026-05-11', '2026-05-12',
    '2026-05-13', '2026-05-14'
]

# NIFTY spot security ID on Dhan = 13
NIFTY_SECURITY_ID = "13"
NSE_IDX = "IDX_I"

def fetch_nifty_1min(from_date, to_date):
    """Fetch NIFTY spot 1-min candles."""
    try:
        resp = dhan.intraday_minute_data(
            security_id=NIFTY_SECURITY_ID,
            exchange_segment=NSE_IDX,
            instrument_type="INDEX",
            interval=1,
            from_date=from_date,
            to_date=to_date
        )
        if resp and 'data' in resp:
            df = pd.DataFrame(resp['data'])
            df['date'] = from_date
            return df
        else:
            print(f"  No data: {resp}")
            return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

print("Fetching NIFTY spot data for manual trade dates...")
all_dfs = []
for d in TRADE_DATES:
    print(f"  Fetching {d}...", end=" ")
    df = fetch_nifty_1min(d, d)
    if df is not None and len(df) > 0:
        print(f"OK ({len(df)} bars)")
        all_dfs.append(df)
    else:
        print("FAILED")
    time.sleep(0.5)  # Rate limit

if all_dfs:
    spot_df = pd.concat(all_dfs, ignore_index=True)
    spot_df.to_parquet(r'c:\cursor\options\niftyopt\data\nifty_spot_2026_manual_dates.parquet')
    print(f"\nSaved {len(spot_df)} rows spot data")
    print(spot_df.head())
else:
    print("\nNo data fetched - will try alternate method")
    # Try historical data API instead
    print("\nTrying historical data API...")
    resp = dhan.historical_minute_charts(
        symbol="NIFTY",
        exchange_segment="NSE_IDX",
        instrument_type="INDEX",
        expiry_code=0,
        from_date="2026-04-30",
        to_date="2026-05-14"
    )
    print(f"Response type: {type(resp)}")
    if resp:
        print(f"Keys: {list(resp.keys()) if isinstance(resp, dict) else 'list'}")
        print(str(resp)[:500])
