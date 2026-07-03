import json
from dhanhq import dhanhq
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Load Dhan tokens
with open(r'c:\cursor\options\niftyopt\config\dhan_tokens.json') as f:
    creds = json.load(f)
TOKEN = creds['access_token']
CLIENT_ID = "1101936133"

dhan = dhanhq(CLIENT_ID, TOKEN)

print("Fetching intraday minute data for NIFTY spot...")
try:
    # NIFTY index security ID is 13, Exchange segment is INDEX
    resp = dhan.intraday_minute_data(
        security_id=13,
        exchange_segment='IDX_LTP',
        instrument_type='INDEX',
        from_date='2026-06-25',
        to_date='2026-06-25',
        interval=1
    )
    print("Response Status:", resp.get("status") if isinstance(resp, dict) else "Non-dict response")
    if isinstance(resp, dict) and resp.get("status") == "success":
        data = resp.get("data", {})
        if "data" in data:
            data = data["data"]
        timestamps = data.get("timestamp", [])
        print("Fetched", len(timestamps), "NIFTY spot candles for June 25!")
    else:
        print("Response:", str(resp)[:300])
except Exception as e:
    print("Error calling API:", e)
