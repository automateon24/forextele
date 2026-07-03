#!/usr/bin/env python3
"""
Find correct security IDs + segments for BN/FN/SENSEX options
and test the EXACT same API call that works for NIFTY options.
"""
import json, time, os
import pandas as pd
import numpy as np

with open('config/dhan_tokens.json') as f:
    token = json.load(f)['access_token']
from dhanhq import dhanhq
dhan = dhanhq('1101936133', token)

# Load security master
df_sec = pd.read_csv('backtest_real_data/dhan_security_master.csv', low_memory=False)
print(f"Security master: {len(df_sec)} rows")
print(f"Segments available: {df_sec['SEM_SEGMENT'].unique()}")
print(f"Instruments available: {df_sec['SEM_INSTRUMENT_NAME'].unique()}")

# ── Find what segment NIFTY options use ─────────────────────────────────────
nifty_opts = df_sec[
    df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith('NIFTY-') &
    df_sec['SEM_INSTRUMENT_NAME'].astype(str).str.contains('OPT', na=False)
]
print(f"\nNIFTY options in master: {len(nifty_opts)}")
if len(nifty_opts) > 0:
    print(f"Segments used by NIFTY opts: {nifty_opts['SEM_SEGMENT'].unique()}")
    nifty_opts['exp_dt'] = pd.to_datetime(nifty_opts['SEM_EXPIRY_DATE'], errors='coerce')
    # Find 2025-03 expiry options (close to our backtest data)
    target = nifty_opts[(nifty_opts['exp_dt'] >= '2025-02-01') & (nifty_opts['exp_dt'] <= '2025-04-01')]
    print(f"NIFTY opts expiring Feb-Mar 2025: {len(target)}")
    if len(target) > 0:
        print(f"Sample: {target.iloc[0][['SEM_SMST_SECURITY_ID','SEM_TRADING_SYMBOL','SEM_EXPIRY_DATE','SEM_SEGMENT','SEM_EXPIRY_CODE']].to_dict()}")

# ── Find BN/FN/SENSEX options with correct segments ─────────────────────────
for idx_name, prefix in [('BANKNIFTY', 'BANKNIFTY-'), ('FINNIFTY', 'FINNIFTY-'), ('SENSEX', 'SENSEX-')]:
    opts = df_sec[
        df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith(prefix) &
        df_sec['SEM_INSTRUMENT_NAME'].astype(str).str.contains('OPT', na=False)
    ]
    print(f"\n{idx_name} options: {len(opts)}")
    if len(opts) > 0:
        print(f"  Segments: {opts['SEM_SEGMENT'].unique()}")
        opts['exp_dt'] = pd.to_datetime(opts['SEM_EXPIRY_DATE'], errors='coerce')
        recent = opts[(opts['exp_dt'] >= '2025-02-01') & (opts['exp_dt'] <= '2025-04-01')].sort_values('exp_dt')
        print(f"  Options expiring Feb-Mar 2025: {len(recent)}")
        if len(recent) > 0:
            print(f"  Sample: {recent.iloc[0][['SEM_SMST_SECURITY_ID','SEM_TRADING_SYMBOL','SEM_EXPIRY_DATE','SEM_SEGMENT']].to_dict()}")

print("\n" + "="*70)
print("TESTING: exact same API call style used for NIFTY option parquets")
print("="*70)

# Read the fetch_2026_rollingoption.py to understand the EXACT API call
with open('fetch_2026_rollingoption.py') as f:
    src = f.read()

# Extract the key function
import re
# Find what security_id and exchange_segment are used for NIFTY options
print("Key parameters used in NIFTY option fetch:")
for line in src.split('\n'):
    if 'security_id' in line.lower() or 'exchange_segment' in line.lower() or 'instrument_type' in line.lower():
        if '#' not in line[:5]:
            print(f"  {line.strip()}")

print("\n" + "="*70)
print("NOW TEST: BN/FN/SENSEX options with their correct security IDs")
print("="*70)

# Dhan segment mapping:
# NSE_FNO = stock + index options on NSE
# BSE_FNO = stock + index options on BSE (SENSEX)
# IDX_I   = index spot only
# The security master 'SEM_SEGMENT' values need to map to Dhan exchange segments

SEGMENT_MAP = {
    'D': 'NSE_FNO',   # NSE Derivatives
    'B': 'BSE_FNO',   # BSE Derivatives  
    'C': 'NSE_FNO',
}

# Test fetching a BANKNIFTY option that existed in Feb 2025
test_indices = []

for idx_name, prefix in [('BANKNIFTY', 'BANKNIFTY-'), ('FINNIFTY', 'FINNIFTY-'), ('SENSEX', 'SENSEX-')]:
    opts = df_sec[
        df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith(prefix) &
        df_sec['SEM_INSTRUMENT_NAME'].astype(str).str.contains('OPT', na=False)
    ].copy()
    if len(opts) == 0:
        continue
    opts['exp_dt'] = pd.to_datetime(opts['SEM_EXPIRY_DATE'], errors='coerce')
    # Find ATM-ish option expiring around Feb 2025
    feb_opts = opts[(opts['exp_dt'] >= '2025-02-01') & (opts['exp_dt'] <= '2025-03-15')].sort_values('exp_dt')
    if len(feb_opts) == 0:
        print(f"{idx_name}: no Feb 2025 options in master")
        continue
    sample = feb_opts.iloc[len(feb_opts)//2]  # middle strike (near ATM)
    seg = str(sample['SEM_SEGMENT'])
    exch_seg = SEGMENT_MAP.get(seg, seg)
    sec_id = str(int(sample['SEM_SMST_SECURITY_ID']))
    
    print(f"\n{idx_name}: Testing sec_id={sec_id}, symbol={sample['SEM_TRADING_SYMBOL']}")
    print(f"  segment={seg} → exchange_segment={exch_seg}, expiry={sample['SEM_EXPIRY_DATE']}")
    
    # Try with instrument_type=OPTIDX
    for inst_type in ['OPTIDX', 'OPTIONS', 'OPT']:
        try:
            resp = dhan.intraday_minute_data(
                security_id=sec_id,
                exchange_segment=exch_seg,
                instrument_type=inst_type,
                interval=1,
                from_date='2025-02-03',
                to_date='2025-02-07'
            )
            status = resp.get('status', 'unknown')
            data = resp.get('data', [])
            if isinstance(data, dict):
                ts = data.get('timestamp', [])
                n_rows = len(ts)
            else:
                n_rows = len(data)
            print(f"  instrument_type={inst_type}: status={status}, rows={n_rows}")
            if n_rows > 0:
                print(f"  SUCCESS! First ts={data['timestamp'][0] if isinstance(data,dict) else data[0]}")
                test_indices.append({
                    'name': idx_name, 'sec_id': sec_id, 'exch_seg': exch_seg,
                    'inst_type': inst_type, 'symbol': sample['SEM_TRADING_SYMBOL']
                })
                break
        except Exception as e:
            print(f"  instrument_type={inst_type}: ERROR {e}")
        time.sleep(0.3)
    time.sleep(0.5)

print(f"\n\nWORKING combinations: {test_indices}")
