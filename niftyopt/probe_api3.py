#!/usr/bin/env python3
"""
Use existing security master CSV to find BN/FN/SENSEX option security IDs,
then test fetching their historical 1-min data via Dhan API.
"""
import json, time, os, glob
import pandas as pd

with open('config/dhan_tokens.json') as f:
    token = json.load(f)['access_token']
from dhanhq import dhanhq
dhan = dhanhq('1101936133', token)

# ── 1. Parse existing security master ─────────────────────────────────────────
print("="*70)
print("STEP 1: Find option security IDs in security master CSV")
print("="*70)

SEC_CSV = 'backtest_real_data/dhan_security_master.csv'
df = pd.read_csv(SEC_CSV, low_memory=False)
print(f"Total rows: {len(df)}")
print(f"Columns: {list(df.columns)}")

# Filter options for our target indices
for idx_symbol in ['BANKNIFTY', 'FINNIFTY', 'NIFTY', 'SENSEX']:
    mask = df['SEM_TRADING_SYMBOL'].astype(str).str.contains(idx_symbol, na=False)
    sub = df[mask]
    # Further filter: option contracts only (OPTIDX instrument type)
    opt_mask = sub['SEM_INSTRUMENT_NAME'].astype(str).str.contains('OPT', na=False)
    opts = sub[opt_mask]
    print(f"\n  {idx_symbol}: {len(sub)} total, {len(opts)} option contracts")
    if len(opts) > 0:
        # Show expiry dates available
        if 'SEM_EXPIRY_DATE' in opts.columns:
            expiries = sorted(opts['SEM_EXPIRY_DATE'].dropna().unique())
            print(f"  Expiry dates: {expiries[:8]}")
        # Show a sample
        print(f"  Sample row: {opts.iloc[0][['SEM_SMST_SECURITY_ID','SEM_TRADING_SYMBOL','SEM_INSTRUMENT_NAME','SEM_EXPIRY_DATE','SEM_STRIKE_PRICE','SEM_SEGMENT','SEM_LOT_UNITS']].to_dict()}")

# ── 2. Understand how existing NIFTY parquets were built ───────────────────────
print("\n" + "="*70)
print("STEP 2: Examine existing NIFTY option parquets to understand fetch pattern")
print("="*70)

pqs = sorted(glob.glob('data/raw/NIFTY_expired_2025-02-03*ATM_CALL*.parquet'))
if pqs:
    df_pq = pd.read_parquet(pqs[0])
    print(f"File: {pqs[0]}")
    print(f"Columns: {list(df_pq.columns)}")
    print(f"Rows: {len(df_pq)}")
    print(f"Sample row:\n{df_pq.iloc[0]}")
    print(f"\nTimestamp range: {df_pq.iloc[0].get('timestamp', 'N/A')} ... {df_pq.iloc[-1].get('timestamp', 'N/A')}")
else:
    print("No NIFTY option parquets found at expected path")

# ── 3. Find the fetch script that created NIFTY option parquets ───────────────
print("\n" + "="*70)
print("STEP 3: How NIFTY options were fetched")
print("="*70)
for fname in ['fetch_2026_rollingoption.py', 'fetch_2026_options.py']:
    if os.path.exists(fname):
        with open(fname) as f:
            print(f"\n--- {fname} ---")
            print(f.read())

# ── 4. Try intraday_minute_data for a specific BN option security ──────────────
print("\n" + "="*70)
print("STEP 4: Test fetching BN/FN option data using security IDs from master")
print("="*70)

# Re-load with proper filtering
df_sec = pd.read_csv(SEC_CSV, low_memory=False)

# Find BANKNIFTY options expiring around Feb-Mar 2025 (same period as NIFTY data)
bn_opts = df_sec[
    df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith('BANKNIFTY') &
    df_sec['SEM_INSTRUMENT_NAME'].astype(str).str.contains('OPT', na=False)
]
fn_opts = df_sec[
    df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith('FINNIFTY') &
    df_sec['SEM_INSTRUMENT_NAME'].astype(str).str.contains('OPT', na=False)
]
sx_opts = df_sec[
    df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith('SENSEX') &
    df_sec['SEM_INSTRUMENT_NAME'].astype(str).str.contains('OPT', na=False)
]

print(f"\nBANKNIFTY options: {len(bn_opts)}")
print(f"FINNIFTY options: {len(fn_opts)}")
print(f"SENSEX options: {len(sx_opts)}")

if len(bn_opts) > 0:
    # Sort by expiry date, find one around 2025-02-03
    bn_opts['exp_dt'] = pd.to_datetime(bn_opts['SEM_EXPIRY_DATE'], errors='coerce')
    recent = bn_opts[bn_opts['exp_dt'] >= '2025-01-01'].sort_values('exp_dt')
    if len(recent) > 0:
        sample = recent.iloc[0]
        print(f"\nBN sample option: {sample[['SEM_SMST_SECURITY_ID','SEM_TRADING_SYMBOL','SEM_EXPIRY_DATE','SEM_STRIKE_PRICE','SEM_SEGMENT']].to_dict()}")
        
        # Try fetching 1-min data for this security
        sec_id = str(int(sample['SEM_SMST_SECURITY_ID']))
        seg    = sample['SEM_SEGMENT']
        # Map segment to Dhan exchange segment
        seg_map = {'NSE_FNO': 'NSE_FNO', 'BSE_FNO': 'BSE_FNO', 
                   'IDX_I': 'IDX_I', 'NSE': 'NSE'}
        exch_seg = seg_map.get(str(seg), str(seg))
        
        print(f"\nFetching: sec_id={sec_id}, segment={exch_seg}, period=2025-02-03 to 2025-02-10")
        try:
            resp = dhan.intraday_minute_data(
                security_id=sec_id,
                exchange_segment=exch_seg,
                instrument_type='OPTIDX',
                interval=1,
                from_date='2025-02-03',
                to_date='2025-02-10'
            )
            print(f"  Status: {resp.get('status')}")
            print(f"  Data rows: {len(resp.get('data', []))}")
            if resp.get('data'):
                print(f"  First row: {resp['data'][0]}")
        except Exception as e:
            print(f"  ERROR: {e}")
