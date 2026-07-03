#!/usr/bin/env python3
"""
Fetch 3 months of spot + option data for BANKNIFTY and FINNIFTY
from Dhan API. Saves to data/raw/ in same format as NIFTY files.

Index configs (Dhan security IDs):
  NIFTY      : sec_id=13,  exchange=IDX_I, atm_step=50,  lot=75
  BANKNIFTY  : sec_id=25,  exchange=IDX_I, atm_step=100, lot=15
  FINNIFTY   : sec_id=27,  exchange=IDX_I, atm_step=50,  lot=40
  MIDCPNIFTY : sec_id=442, exchange=IDX_I, atm_step=25,  lot=75

For options we use Dhan's historical_daily_data for EOD chain
and intraday_minute_data for 1-min spot.
Note: Dhan does NOT provide historical option 1-min data via the free API.
We therefore fetch:
  - 1-min SPOT for each index (same API that works for NIFTY)
  - Daily EOD for each index (OHLCV)

The backtest engine will be adapted to work with SPOT data directly
(reconstruct option premiums from spot OHLC using proxy model)
rather than requiring actual option parquets.
"""
import sys, json, time, os
sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd
from dhanhq import dhanhq

TOKEN_FILE = r'c:\cursor\options\niftyopt\config\dhan_tokens.json'
with open(TOKEN_FILE) as f:
    token = json.load(f)['access_token']
dhan = dhanhq("1101936133", token)

OUT_DIR = r'c:\cursor\options\niftyopt\data\raw'
SPOT_DIR = r'c:\cursor\options\niftyopt\data\spot_multi'
os.makedirs(SPOT_DIR, exist_ok=True)

# 3 months: March, April, May 2026
CHUNKS = [
    ('2026-03-01', '2026-03-31'),
    ('2026-04-01', '2026-04-30'),
    ('2026-05-01', '2026-05-27'),
    # Also backfill 2025 for more data
    ('2025-02-03', '2025-03-05'),
    ('2025-03-05', '2025-04-04'),
    ('2025-04-04', '2025-05-04'),
]

INDICES = {
    'BANKNIFTY': {'sec_id': '25',  'exchange': 'IDX_I', 'atm_step': 100},
    'FINNIFTY':  {'sec_id': '27',  'exchange': 'IDX_I', 'atm_step': 50},
}

# Also fetch EOD for BANKNIFTY / FINNIFTY
EOD_CHUNKS = [
    ('2023-01-01', '2023-12-31'),
    ('2024-01-01', '2024-12-31'),
    ('2025-01-01', '2025-12-31'),
    ('2026-01-01', '2026-05-27'),
]

print("="*60)
print("FETCHING MULTI-INDEX SPOT DATA (1-min intraday)")
print("="*60)

for idx_name, cfg in INDICES.items():
    all_dfs = []
    print(f"\n--- {idx_name} ---")
    for from_d, to_d in CHUNKS:
        print(f"  {from_d} → {to_d} ...", end=" ", flush=True)
        try:
            resp = dhan.intraday_minute_data(
                security_id=cfg['sec_id'],
                exchange_segment=cfg['exchange'],
                instrument_type="INDEX",
                interval=1,
                from_date=from_d,
                to_date=to_d
            )
            if resp and 'data' in resp and resp['data']:
                df = pd.DataFrame(resp['data'])
                df['ts'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)\
                             .dt.tz_convert('Asia/Kolkata')
                df['date_str'] = df['ts'].dt.strftime('%Y-%m-%d')
                df['hhmm'] = df['ts'].dt.hour * 100 + df['ts'].dt.minute
                df = df[(df['hhmm'] >= 915) & (df['hhmm'] <= 1530)]
                df['index'] = idx_name
                days = df['date_str'].nunique()
                rows = len(df)
                print(f"OK — {rows:,} bars, {days} days")
                all_dfs.append(df)
                chunk_file = os.path.join(SPOT_DIR,
                    f"{idx_name}_spot_{from_d[:7]}.parquet")
                df.to_parquet(chunk_file)
            else:
                print(f"EMPTY — {resp}")
        except Exception as e:
            print(f"ERROR — {e}")
        time.sleep(1.5)

    if all_dfs:
        combined = pd.concat(all_dfs).sort_values('ts').reset_index(drop=True)
        out = os.path.join(SPOT_DIR, f"{idx_name}_spot_full.parquet")
        combined.to_parquet(out)
        print(f"  SAVED: {out} ({len(combined):,} rows, "
              f"{combined['date_str'].nunique()} days)")

print("\n" + "="*60)
print("FETCHING EOD DATA FOR BANKNIFTY + FINNIFTY")
print("="*60)

for idx_name, cfg in INDICES.items():
    all_eod = []
    print(f"\n--- {idx_name} EOD ---")
    for from_d, to_d in EOD_CHUNKS:
        print(f"  {from_d} → {to_d} ...", end=" ", flush=True)
        try:
            resp = dhan.historical_daily_data(
                security_id=cfg['sec_id'],
                exchange_segment=cfg['exchange'],
                instrument_type="INDEX",
                from_date=from_d,
                to_date=to_d
            )
            if resp and 'data' in resp and resp['data']:
                df = pd.DataFrame(resp['data'])
                df['dt'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)\
                              .dt.tz_convert('Asia/Kolkata').dt.date
                df['index'] = idx_name
                print(f"OK — {len(df)} days")
                all_eod.append(df)
            else:
                print(f"EMPTY — {resp}")
        except Exception as e:
            print(f"ERROR — {e}")
        time.sleep(1.0)

    if all_eod:
        combined = pd.concat(all_eod).drop_duplicates('dt').sort_values('dt').reset_index(drop=True)
        out = os.path.join(SPOT_DIR, f"{idx_name}_eod.parquet")
        combined.to_parquet(out)
        print(f"  SAVED: {out} ({len(combined)} days)")

print("\nDone. Check data/spot_multi/ for results.")
