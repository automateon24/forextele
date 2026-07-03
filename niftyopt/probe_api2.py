#!/usr/bin/env python3
"""
Deep probe: find correct security IDs for option contracts using security master CSV
and test historical option data fetch via Dhan API for BANKNIFTY, FINNIFTY, SENSEX.
"""
import json, time, csv, io, os
import pandas as pd
import requests

with open('config/dhan_tokens.json') as f:
    token = json.load(f)['access_token']
from dhanhq import dhanhq
dhan = dhanhq('1101936133', token)

print("="*70)
print("PROBE: Security master CSV for option contracts")
print("="*70)

# Dhan provides a security master CSV — check if we have it
SEC_CSV = 'backtest_real_data/dhan_security_master.csv'
if os.path.exists(SEC_CSV):
    df = pd.read_csv(SEC_CSV)
    print(f"Security master loaded: {len(df)} rows, columns: {list(df.columns)[:10]}")
    # Filter for option contracts of our target indices
    for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
        sub = df[df.apply(lambda r: idx in str(r).upper(), axis=1)]
        if len(sub) > 0:
            print(f"\n  {idx}: {len(sub)} contracts found")
            print(f"  Sample: {sub.iloc[0].to_dict()}")
else:
    print(f"Not found: {SEC_CSV}")

print("\n" + "="*70)
print("PROBE: Download fresh security master from Dhan")
print("="*70)
# Dhan's security master URL
for url in [
    'https://images.dhan.co/api-data/api-scrip-master.csv',
    'https://images.dhan.co/api-data/api-scrip-master-NSE.csv',
]:
    try:
        print(f"Trying: {url}")
        r = requests.get(url, timeout=15)
        print(f"  Status: {r.status_code}, size: {len(r.content)} bytes")
        if r.status_code == 200 and len(r.content) > 1000:
            # Parse first few rows
            text = r.text[:3000]
            lines = text.strip().split('\n')
            print(f"  Header: {lines[0][:200]}")
            print(f"  Row 1:  {lines[1][:200] if len(lines)>1 else 'none'}")
            # Save it
            with open('backtest_real_data/dhan_security_master_fresh.csv', 'w') as f:
                f.write(r.text)
            print(f"  SAVED to dhan_security_master_fresh.csv ({len(lines)} rows)")
            break
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "="*70)
print("PROBE: fetch_security_list with correct mode")
print("="*70)
import inspect
print("fetch_security_list signature:", inspect.signature(dhan.fetch_security_list))

# Try with 'compact' mode
for mode in ['compact', 'detailed']:
    try:
        r = dhan.fetch_security_list(mode)
        if r and len(r) > 100:
            print(f"  mode={mode}: {len(r)} chars")
            # Try to parse
            lines = r.strip().split('\n')
            print(f"  Header: {lines[0][:200]}")
            # Find BN/FN/SENSEX option rows
            for line in lines[1:500]:
                if any(x in line.upper() for x in ['BANKNIFTY', 'FINNIFTY', 'SENSEX']):
                    if 'OPTIDX' in line or 'CE' in line or 'PE' in line:
                        print(f"  Option row: {line[:200]}")
                        break
            break
        else:
            print(f"  mode={mode}: empty or small ({len(r) if r else 0})")
    except Exception as e:
        print(f"  mode={mode}: {e}")

print("\n" + "="*70)
print("PROBE: intraday_minute_data for known option security IDs")
print("  (NIFTY options are fetched via the expired contract parquets)")
print("  Checking if BN/FN/SENSEX options can be fetched the SAME WAY")
print("="*70)

# NIFTY uses security_id=13 with instrument_type=INDEX for spot
# For options, it uses the parquet filenames which are Dhan API responses stored to disk
# Let's look at an existing NIFTY option parquet to understand the actual security_id used
nifty_sample = 'data/raw/NIFTY_expired_2025-02-03_2025-03-05_ATM_CALL_1min_MONTH_1.parquet'
if os.path.exists(nifty_sample):
    df = pd.read_parquet(nifty_sample)
    print(f"NIFTY option parquet columns: {list(df.columns)}")
    print(f"Sample row: {df.iloc[0].to_dict()}")
    print(f"Rows: {len(df)}, date range: {df.index.min() if df.index.name else 'index-based'}")
else:
    print(f"Not found: {nifty_sample}")
    # Find any NIFTY parquet
    import glob
    pqs = glob.glob('data/raw/NIFTY_expired_2025-02-03*ATM_CALL*.parquet')
    if pqs:
        df = pd.read_parquet(pqs[0])
        print(f"Found {pqs[0]}: columns={list(df.columns)}")
        print(f"Sample: {df.iloc[0].to_dict()}")

print("\n" + "="*70)
print("PROBE: How were NIFTY option parquets fetched? Check fetch scripts")
print("="*70)
for fname in ['fetch_2026_options.py', 'fetch_2026_rollingoption.py']:
    if os.path.exists(fname):
        with open(fname) as f:
            content = f.read()
        print(f"\n--- {fname} ---")
        print(content[:2000])
