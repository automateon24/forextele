"""
Fetch maximum 2026 NIFTY spot 1-min data from Dhan API.
Dhan allows up to 1 month per request for intraday minute data.
We fetch Jan 2026 - May 2026 in monthly chunks.
"""
import sys, json, time, os
sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd
from dhanhq import dhanhq

token_file = r'c:\cursor\options\niftyopt\config\dhan_tokens.json'
with open(token_file) as f:
    token = json.load(f)['access_token']
dhan = dhanhq("1101936133", token)

# Dhan allows max ~1 month per intraday call
# Fetch Jan 2026 through May 27 2026 in chunks
CHUNKS = [
    ('2026-01-01', '2026-01-31'),
    ('2026-02-01', '2026-02-28'),
    ('2026-03-01', '2026-03-31'),
    ('2026-04-01', '2026-04-30'),
    ('2026-05-01', '2026-05-27'),
]

NIFTY_SEC_ID = "13"
NSE_IDX = "IDX_I"
OUT_DIR = r'c:\cursor\options\niftyopt\data\spot_2026'
os.makedirs(OUT_DIR, exist_ok=True)

all_dfs = []
for from_d, to_d in CHUNKS:
    print(f"Fetching NIFTY spot {from_d} → {to_d} ...", end=" ", flush=True)
    try:
        resp = dhan.intraday_minute_data(
            security_id=NIFTY_SEC_ID,
            exchange_segment=NSE_IDX,
            instrument_type="INDEX",
            interval=1,
            from_date=from_d,
            to_date=to_d
        )
        if resp and 'data' in resp and resp['data']:
            df = pd.DataFrame(resp['data'])
            # Normalize timestamp
            df['ts'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
            df['date_str'] = df['ts'].dt.strftime('%Y-%m-%d')
            df['hhmm'] = df['ts'].dt.hour * 100 + df['ts'].dt.minute
            # Only keep market hours
            df = df[(df['hhmm'] >= 915) & (df['hhmm'] <= 1530)]
            days = df['date_str'].nunique()
            rows = len(df)
            print(f"OK — {rows} bars, {days} trading days")
            all_dfs.append(df)
            # Save per-chunk
            chunk_file = os.path.join(OUT_DIR, f"nifty_spot_{from_d[:7]}.parquet")
            df.to_parquet(chunk_file)
            print(f"  Saved: {chunk_file}")
        else:
            print(f"EMPTY — {resp}")
    except Exception as e:
        print(f"ERROR — {e}")
    time.sleep(1.0)

if all_dfs:
    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sort_values('ts').reset_index(drop=True)
    combined_path = r'c:\cursor\options\niftyopt\data\nifty_spot_2026_full.parquet'
    combined.to_parquet(combined_path)
    total_days = combined['date_str'].nunique()
    print(f"\n{'='*60}")
    print(f"TOTAL: {len(combined):,} bars | {total_days} trading days")
    print(f"Date range: {combined['date_str'].min()} → {combined['date_str'].max()}")
    print(f"Saved: {combined_path}")
else:
    print("No data fetched!")
