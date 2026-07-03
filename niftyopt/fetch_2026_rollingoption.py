"""
Fetch NIFTY options 1-min data for Jan 2026 - May 2026
using Dhan /charts/rollingoption API (same as existing 2025 parquets).
Saves in identical format so BACKTEST_V3_TUNED.py runs without changes.
"""
import sys, json, time, os, requests
sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Load token
with open(r'c:\cursor\options\niftyopt\config\dhan_tokens.json') as f:
    creds = json.load(f)
TOKEN = creds['access_token']
CLIENT_ID = "1101936133"

BASE_URL = "https://api.dhan.co/v2"
HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'access-token': TOKEN,
    'client-id': CLIENT_ID
}

RAW_DIR = r'c:\cursor\options\niftyopt\data\raw'
os.makedirs(RAW_DIR, exist_ok=True)

# Dhan rolling option API — 30-day max per call
# We'll fetch 3 monthly chunks: Jan-Mar, Mar-Apr, Apr-May 2026
# Each chunk gets ATM, ATM+1..+4, ATM-1..-4 × CALL/PUT = 18 files per chunk

PERIODS = [
    ('2026-01-02', '2026-01-31'),
    ('2026-02-01', '2026-02-28'),
    ('2026-03-01', '2026-03-31'),
    ('2026-04-01', '2026-04-30'),
    ('2026-05-01', '2026-05-27'),
]

STRIKES   = ['ATM', 'ATM+1', 'ATM-1', 'ATM+2', 'ATM-2', 'ATM+3', 'ATM-3']
OPT_TYPES = ['CALL', 'PUT']

def fetch_rolling_option(from_date, to_date, strike, opt_type, expiry_flag='MONTH', expiry_code=1):
    payload = {
        "exchangeSegment": "NSE_FNO",
        "interval": "1",
        "securityId": 13,
        "instrument": "OPTIDX",
        "expiryFlag": expiry_flag,
        "expiryCode": expiry_code,
        "strike": strike,
        "drvOptionType": opt_type,
        "requiredData": ["open", "high", "low", "close", "iv", "volume", "oi", "spot"],
        "fromDate": from_date,
        "toDate": to_date
    }
    try:
        r = requests.post(f"{BASE_URL}/charts/rollingoption", json=payload, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"    HTTP {r.status_code}: {r.text[:200]}")
            return None
    except Exception as e:
        print(f"    Exception: {e}")
        return None

def parse_response(resp, strike, opt_type, from_date, to_date):
    """Parse the rolling option response into a DataFrame matching existing parquet format.
    API returns: {"data": {"ce": {...arrays...}, "pe": {...arrays...}}}
    """
    if not resp or 'data' not in resp:
        return pd.DataFrame()
    outer = resp['data']
    if not outer:
        return pd.DataFrame()

    # Pick the right sub-key: ce for CALL, pe for PUT
    sub_key = 'ce' if opt_type == 'CALL' else 'pe'
    data = outer.get(sub_key)
    if not data:
        # Some responses have flat structure (no ce/pe nesting)
        data = outer

    timestamps = data.get('timestamp', [])
    if not timestamps:
        return pd.DataFrame()

    df = pd.DataFrame({
        'timestamp': pd.to_datetime(timestamps, unit='s', utc=True).tz_convert('Asia/Kolkata').tz_localize(None),
        'open':   data.get('open',   [np.nan]*len(timestamps)),
        'high':   data.get('high',   [np.nan]*len(timestamps)),
        'low':    data.get('low',    [np.nan]*len(timestamps)),
        'close':  data.get('close',  [np.nan]*len(timestamps)),
        'volume': data.get('volume', [0]*len(timestamps)),
        'iv':     data.get('iv',     [0]*len(timestamps)),
        'oi':     data.get('oi',     [0]*len(timestamps)),
        'spot':   data.get('spot',   [np.nan]*len(timestamps)),
    })
    df['option_type']     = 'CE' if opt_type == 'CALL' else 'PE'
    df['strike']          = strike
    df['symbol']          = 'NIFTY'
    df['strike_position'] = strike
    df['interval']        = 1
    df['expiry_flag']     = 'MONTH'
    df['expiry_code']     = 1
    # Filter market hours only
    df['hhmm'] = df['timestamp'].dt.hour * 100 + df['timestamp'].dt.minute
    df = df[(df['hhmm'] >= 915) & (df['hhmm'] <= 1530)].drop(columns=['hhmm'])
    return df

total_files = 0
total_rows  = 0

for ps, pe in PERIODS:
    print(f"\n{'='*60}")
    print(f"Period: {ps} → {pe}")
    print(f"{'='*60}")
    for strike in STRIKES:
        for opt_type in OPT_TYPES:
            fname = f"NIFTY_expired_{ps}_{pe}_{strike}_{opt_type}_1min_MONTH_1.parquet"
            fpath = os.path.join(RAW_DIR, fname)

            if os.path.exists(fpath):
                print(f"  SKIP (exists): {fname}")
                total_files += 1
                continue

            print(f"  Fetching {strike} {opt_type} ...", end=" ", flush=True)
            resp = fetch_rolling_option(ps, pe, strike, opt_type)
            df = parse_response(resp, strike, opt_type, ps, pe)

            if df.empty:
                print("EMPTY")
            else:
                df.to_parquet(fpath, index=False)
                rows = len(df)
                days = df['timestamp'].dt.date.nunique()
                print(f"OK — {rows} bars, {days} trading days → {fname}")
                total_files += 1
                total_rows  += rows

            time.sleep(0.4)  # Rate limit: ~2.5 calls/sec

print(f"\n{'='*60}")
print(f"DONE: {total_files} files, {total_rows:,} total rows")
print(f"Saved to: {RAW_DIR}")
print()

# Verify new data is loadable
print("Verifying new data loads in backtest format...")
frames = []
for ps, pe in PERIODS:
    for strike in STRIKES:
        for ot in OPT_TYPES:
            fp = os.path.join(RAW_DIR, f"NIFTY_expired_{ps}_{pe}_{strike}_{ot}_1min_MONTH_1.parquet")
            if os.path.exists(fp):
                df = pd.read_parquet(fp)
                df['option_type_flag'] = 'CE' if ot == 'CALL' else 'PE'
                frames.append(df)

if frames:
    combined = pd.concat(frames, ignore_index=True)
    combined['timestamp'] = pd.to_datetime(combined['timestamp'])
    combined['ts_ist'] = combined['timestamp']
    combined['date'] = combined['ts_ist'].dt.date
    print(f"  Total rows: {len(combined):,}")
    print(f"  Trading days: {combined['date'].nunique()}")
    print(f"  Date range: {combined['date'].min()} → {combined['date'].max()}")
    print("  Columns:", combined.columns.tolist())
    print()
    print("2026 data ready for backtest!")
else:
    print("  No 2026 files found yet — check fetch above")
