#!/usr/bin/env python3
"""Verify all fetched multi-index option data."""
import glob, os
import pandas as pd

RAW_DIR = 'data/raw'

print("="*65)
print("MULTI-INDEX OPTION DATA VERIFICATION")
print("="*65)

for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
    pqs = sorted(glob.glob(os.path.join(RAW_DIR, f'{idx}_expired_*_CALL_1min_MONTH_1.parquet')))
    if not pqs:
        # NIFTY uses different naming
        pqs = sorted(glob.glob(os.path.join(RAW_DIR, f'{idx}_expired_*ATM_CALL*.parquet')))
    total_rows = 0
    all_days = set()
    for p in pqs:
        df = pd.read_parquet(p)
        total_rows += len(df)
        ts = pd.to_datetime(df['timestamp'])
        all_days.update(ts.dt.date.unique())
    if all_days:
        print(f"\n  {idx}:")
        print(f"    Files   : {len(pqs)} (ATM CALL only)")
        print(f"    Rows    : {total_rows:,}")
        print(f"    Days    : {len(all_days)} trading days")
        print(f"    Range   : {min(all_days)} → {max(all_days)}")
        # Show a sample row
        if pqs:
            sample = pd.read_parquet(pqs[0]).iloc[100]
            print(f"    Sample  : close={sample['close']:.2f}, spot={sample['spot']:.2f}, iv={sample.get('iv',0):.2f}")
    else:
        print(f"\n  {idx}: NO DATA")

print("\n" + "="*65)
print("FULL STRIKE COUNT (all strikes × CE+PE)")
print("="*65)

for idx in ['BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
    all_pqs = sorted(glob.glob(os.path.join(RAW_DIR, f'{idx}_expired_*1min_MONTH_1.parquet')))
    total_rows = 0
    all_days = set()
    for p in all_pqs:
        df = pd.read_parquet(p)
        total_rows += len(df)
        ts = pd.to_datetime(df['timestamp'])
        all_days.update(ts.dt.date.unique())
    print(f"  {idx}: {len(all_pqs)} files, {total_rows:,} rows, {len(all_days)} days")
