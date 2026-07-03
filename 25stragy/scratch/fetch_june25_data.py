import sys
import json
import time
import os
import requests
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

# Read Dhan credentials
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

INDICES = {
    'NIFTY':      {'sec_id': 13,  'exch': 'NSE_FNO'},
    'BANKNIFTY':  {'sec_id': 25,  'exch': 'NSE_FNO'},
    'FINNIFTY':   {'sec_id': 27,  'exch': 'NSE_FNO'},
    'MIDCPNIFTY': {'sec_id': 442, 'exch': 'NSE_FNO'},
    'SENSEX':     {'sec_id': 51,  'exch': 'BSE_FNO'},
}

STRIKES   = ['ATM', 'ATM+1', 'ATM-1', 'ATM+2', 'ATM-2', 'ATM+3', 'ATM-3']
OPT_TYPES = ['CALL', 'PUT']

def fetch_rolling_option(sec_id, exch, from_date, to_date, strike, opt_type):
    payload = {
        "exchangeSegment": exch,
        "interval": "1",
        "securityId": sec_id,
        "instrument": "OPTIDX",
        "expiryFlag": "MONTH",
        "expiryCode": 1,
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
    df['hhmm'] = df['timestamp'].dt.hour * 100 + df['timestamp'].dt.minute
    df = df[(df['hhmm'] >= 915) & (df['hhmm'] <= 1530)].drop(columns=['hhmm'])
    return df

# Main Fetch Loop for June 25, 2026
date_str = "2026-06-25"
print(f"Starting fetch for {date_str} options data...")

for idx_name, cfg in INDICES.items():
    print(f"\nIndex: {idx_name}...")
    for strike in STRIKES:
        for opt_type in OPT_TYPES:
            fname = f"{idx_name}_expired_{date_str}_{date_str}_{strike}_{opt_type}_1min_MONTH_1.parquet"
            fpath = os.path.join(RAW_DIR, fname)
            
            print(f"  Fetching {strike} {opt_type}...", end="", flush=True)
            resp = fetch_rolling_option(cfg['sec_id'], cfg['exch'], date_str, date_str, strike, opt_type)
            df = parse_response(resp, idx_name, strike, opt_type)
            
            if df.empty:
                print(" -> EMPTY / ERROR")
            else:
                df.to_parquet(fpath, index=False)
                print(f" -> OK ({len(df)} rows)")
            time.sleep(0.5)

print("\nFetch completed successfully!")
