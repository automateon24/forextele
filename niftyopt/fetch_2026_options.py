"""
Fetch NIFTY options 1-min data for Jan-May 2026 from Dhan API.
Uses the same parquet format as existing 2025 data so backtest runs unchanged.

Approach:
 1. Load the 2026 spot data (already fetched)
 2. For each trading week, determine approximate ATM strike from spot
 3. Fetch option chain intraday for that week's expiry strikes (ATM ± 3)
 4. Save as parquets in data/raw/ with naming matching existing format
"""
import sys, json, time, os, math
sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd
import numpy as np
from datetime import date, timedelta
from dhanhq import dhanhq

token_file = r'c:\cursor\options\niftyopt\config\dhan_tokens.json'
with open(token_file) as f:
    token = json.load(f)['access_token']
dhan = dhanhq("1101936133", token)

# Load the 2026 spot data we already fetched
spot_df = pd.read_parquet(r'c:\cursor\options\niftyopt\data\nifty_spot_2026_full.parquet')
spot_df['date_str'] = spot_df['ts'].dt.strftime('%Y-%m-%d')

# Get daily open/close to estimate ATM
daily_spot = spot_df.groupby('date_str').agg(
    open=('open', 'first'),
    close=('close', 'last'),
    high=('high', 'max'),
    low=('low', 'min')
).reset_index()

print(f"Spot data: {len(daily_spot)} trading days")
print(daily_spot.head())

# Step 1: Check what option_chain gives us for a sample date
print("\nChecking option_chain API...")
try:
    oc = dhan.option_chain(
        UnderlyingSecurityId="13",
        UnderlyingExchangeSegment="IDX_I",
        ExpiryDate="2026-01-08"
    )
    print(f"option_chain response type: {type(oc)}")
    if isinstance(oc, dict):
        print(f"Keys: {list(oc.keys())}")
        if 'data' in oc:
            print(f"data type: {type(oc['data'])}, len={len(oc['data']) if oc['data'] else 0}")
            if oc['data']:
                first = oc['data'][0] if isinstance(oc['data'], list) else oc['data']
                print(f"First entry keys: {list(first.keys()) if isinstance(first, dict) else first}")
    else:
        print(str(oc)[:300])
except Exception as e:
    print(f"option_chain error: {e}")

# Step 2: Check expiry_list
print("\nChecking expiry_list API...")
try:
    el = dhan.expiry_list(
        UnderlyingSecurityId="13",
        UnderlyingExchangeSegment="IDX_I"
    )
    print(f"expiry_list type: {type(el)}")
    if isinstance(el, dict) and 'data' in el:
        expiries = el['data']
        print(f"Available expiries (first 10): {expiries[:10] if expiries else 'None'}")
    else:
        print(str(el)[:300])
except Exception as e:
    print(f"expiry_list error: {e}")

# Step 3: Check intraday_minute_data for an option
print("\nChecking intraday_minute_data for NIFTY option...")
# NIFTY option security IDs need to be fetched from fetch_security_list
try:
    # Try fetching security list for NIFTY options
    print("Checking fetch_security_list...")
    help_text = str(dhan.fetch_security_list.__doc__)
    print(f"  fetch_security_list doc: {help_text[:200]}")
except Exception as e:
    print(f"  fetch_security_list error: {e}")

