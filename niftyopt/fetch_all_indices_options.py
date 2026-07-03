#!/usr/bin/env python3
"""
Fetch real 1-min option data for BANKNIFTY, FINNIFTY, MIDCPNIFTY, SENSEX
using the same /v2/charts/rollingoption API that works for NIFTY.

Saves in identical parquet format as NIFTY parquets so backtest runs unchanged.
"""
import sys, json, time, os, requests
sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd
import numpy as np

with open(r'c:\cursor\options\niftyopt\config\dhan_tokens.json') as f:
    creds = json.load(f)
TOKEN     = creds['access_token']
CLIENT_ID = "1101936133"
BASE_URL  = "https://api.dhan.co/v2"
HEADERS   = {
    'Content-Type':  'application/json',
    'Accept':        'application/json',
    'access-token':  TOKEN,
    'client-id':     CLIENT_ID
}

RAW_DIR = r'c:\cursor\options\niftyopt\data\raw'
os.makedirs(RAW_DIR, exist_ok=True)

# ── Index configs (all confirmed working above) ────────────────────────────────
INDICES = {
    'BANKNIFTY':  {'sec_id': 25,  'exch': 'NSE_FNO', 'atm_step': 100, 'lot': 15},
    'FINNIFTY':   {'sec_id': 27,  'exch': 'NSE_FNO', 'atm_step': 50,  'lot': 40},
    'MIDCPNIFTY': {'sec_id': 442, 'exch': 'NSE_FNO', 'atm_step': 25,  'lot': 75},
    'SENSEX':     {'sec_id': 51,  'exch': 'BSE_FNO', 'atm_step': 100, 'lot': 10},
}

# All periods that match existing NIFTY data
PERIODS = [
    ('2025-02-03', '2025-03-05'),
    ('2025-03-05', '2025-04-04'),
    ('2025-04-04', '2025-05-04'),
    ('2026-01-02', '2026-01-31'),
    ('2026-02-01', '2026-02-28'),
    ('2026-03-01', '2026-03-31'),
    ('2026-04-01', '2026-04-30'),
    ('2026-05-01', '2026-05-27'),
]

STRIKES   = ['ATM', 'ATM+1', 'ATM-1', 'ATM+2', 'ATM-2', 'ATM+3', 'ATM-3']
OPT_TYPES = ['CALL', 'PUT']


def fetch_rolling_option(sec_id, exch, from_date, to_date, strike, opt_type,
                          expiry_flag='MONTH', expiry_code=1):
    payload = {
        "exchangeSegment": exch,
        "interval": "1",
        "securityId": sec_id,
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
        r = requests.post(f"{BASE_URL}/charts/rollingoption",
                          json=payload, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"    HTTP {r.status_code}: {r.text[:150]}")
            return None
    except Exception as e:
        print(f"    Exception: {e}")
        return None


def parse_response(resp, idx_name, strike, opt_type):
    if not resp or 'data' not in resp:
        return pd.DataFrame()
    outer = resp['data']
    if not outer:
        return pd.DataFrame()

    sub_key = 'ce' if opt_type == 'CALL' else 'pe'
    data = outer.get(sub_key) or outer

    timestamps = data.get('timestamp', [])
    if not timestamps:
        return pd.DataFrame()

    df = pd.DataFrame({
        'timestamp': pd.to_datetime(timestamps, unit='s', utc=True)
                        .tz_convert('Asia/Kolkata').tz_localize(None),
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
    df['symbol']          = idx_name
    df['strike_position'] = strike
    df['interval']        = 1
    df['expiry_flag']     = 'MONTH'
    df['expiry_code']     = 1
    # Market hours only
    df['hhmm'] = df['timestamp'].dt.hour * 100 + df['timestamp'].dt.minute
    df = df[(df['hhmm'] >= 915) & (df['hhmm'] <= 1530)].drop(columns=['hhmm'])
    return df


# ── MAIN FETCH LOOP ────────────────────────────────────────────────────────────
total_files = 0
total_rows  = 0
skipped     = 0
errors      = 0

for idx_name, cfg in INDICES.items():
    print(f"\n{'='*65}")
    print(f"INDEX: {idx_name}  (sec_id={cfg['sec_id']}, exch={cfg['exch']}, lot={cfg['lot']})")
    print(f"{'='*65}")

    for ps, pe in PERIODS:
        print(f"\n  Period: {ps} → {pe}")
        for strike in STRIKES:
            for opt_type in OPT_TYPES:
                fname = f"{idx_name}_expired_{ps}_{pe}_{strike}_{opt_type}_1min_MONTH_1.parquet"
                fpath = os.path.join(RAW_DIR, fname)

                if os.path.exists(fpath):
                    existing = pd.read_parquet(fpath)
                    if len(existing) > 100:
                        print(f"    SKIP (exists, {len(existing)} rows): {fname}")
                        skipped += 1
                        total_files += 1
                        continue

                print(f"    Fetching {strike} {opt_type} ...", end=" ", flush=True)
                resp = fetch_rolling_option(
                    cfg['sec_id'], cfg['exch'], ps, pe, strike, opt_type
                )
                df = parse_response(resp, idx_name, strike, opt_type)

                if df.empty:
                    print(f"EMPTY (resp={str(resp)[:80] if resp else 'None'})")
                    errors += 1
                else:
                    df.to_parquet(fpath, index=False)
                    rows = len(df)
                    days = df['timestamp'].dt.date.nunique()
                    print(f"OK — {rows:,} bars, {days} days")
                    total_files += 1
                    total_rows  += rows

                time.sleep(0.4)

print(f"\n{'='*65}")
print(f"FETCH COMPLETE")
print(f"  Files saved : {total_files}")
print(f"  Skipped     : {skipped}")
print(f"  Errors      : {errors}")
print(f"  Total rows  : {total_rows:,}")
print(f"  Saved to    : {RAW_DIR}")
print(f"{'='*65}")

# ── VERIFY ────────────────────────────────────────────────────────────────────
print("\nVerifying data can be loaded...")
import glob
for idx_name in INDICES:
    pqs = glob.glob(os.path.join(RAW_DIR, f"{idx_name}_expired_*ATM_CALL*.parquet"))
    if pqs:
        frames = [pd.read_parquet(p) for p in pqs]
        combined = pd.concat(frames, ignore_index=True)
        combined['date'] = pd.to_datetime(combined['timestamp']).dt.date
        print(f"  {idx_name}: {len(combined):,} rows, {combined['date'].nunique()} trading days, "
              f"spot range {combined['spot'].min():.0f}–{combined['spot'].max():.0f}")
    else:
        print(f"  {idx_name}: no files found")
