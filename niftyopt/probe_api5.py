#!/usr/bin/env python3
"""
Final probe:
1. Check what expiry dates exist in security master for BN/FN/SENSEX
2. Download fresh security master from Dhan (has current + recent contracts)
3. Find correct security IDs for options in the backtest date range
"""
import json, time, os
import pandas as pd

with open('config/dhan_tokens.json') as f:
    token = json.load(f)['access_token']
from dhanhq import dhanhq
dhan = dhanhq('1101936133', token)

df_sec = pd.read_csv('backtest_real_data/dhan_security_master.csv', low_memory=False)

print("="*70)
print("What expiry dates exist in the security master for each index?")
print("="*70)

for idx_name, prefix in [('NIFTY', 'NIFTY-'), ('BANKNIFTY', 'BANKNIFTY-'), ('FINNIFTY', 'FINNIFTY-'), ('SENSEX', 'SENSEX-')]:
    opts = df_sec[
        df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith(prefix) &
        df_sec['SEM_INSTRUMENT_NAME'].astype(str).str.isin(['OPTIDX'])
    ].copy()
    opts['exp_dt'] = pd.to_datetime(opts['SEM_EXPIRY_DATE'], errors='coerce')
    expiries = sorted(opts['exp_dt'].dropna().unique())
    print(f"\n{idx_name}: {len(opts)} contracts, expiry range: {expiries[0].date() if expiries else 'none'} to {expiries[-1].date() if expiries else 'none'}")
    if expiries:
        print(f"  First 3: {[str(e.date()) for e in expiries[:3]]}")
        print(f"  Last 3:  {[str(e.date()) for e in expiries[-3:]]}")

print("\n" + "="*70)
print("How were NIFTY option parquets actually fetched? Check fetch_2026_rollingoption.py")
print("="*70)

with open('fetch_2026_rollingoption.py') as f:
    src = f.read()
# Show the key fetch function
lines = src.split('\n')
for i, line in enumerate(lines):
    if 'def fetch_rolling' in line or 'historical_daily_data' in line or 'intraday_minute_data' in line or 'expiry_code' in line.lower():
        print(f"  L{i+1}: {line}")

print("\n" + "="*70)
print("CRITICAL: Test historical_daily_data with expiry_code for BN options")
print("="*70)

# The NIFTY option fetch uses historical_daily_data with expiry_code
# Let's test this for BN/FN/SENSEX

# First find the correct security IDs from master for FUTURE expiries (what the master has)
for idx_name, prefix, spot_id, exch in [
    ('BANKNIFTY', 'BANKNIFTY-', '25',  'NSE_FNO'),
    ('FINNIFTY',  'FINNIFTY-',  '27',  'NSE_FNO'),
    ('SENSEX',    'SENSEX-',    '51',  'BSE_FNO'),
]:
    opts = df_sec[
        df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith(prefix) &
        df_sec['SEM_INSTRUMENT_NAME'].astype(str).str.isin(['OPTIDX'])
    ].copy()
    if len(opts) == 0:
        print(f"{idx_name}: no OPTIDX found — trying OPTSTK...")
        opts = df_sec[
            df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith(prefix) &
            df_sec['SEM_INSTRUMENT_NAME'].astype(str).str.contains('OPT', na=False)
        ].copy()

    opts['exp_dt'] = pd.to_datetime(opts['SEM_EXPIRY_DATE'], errors='coerce')
    # Use nearest future expiry
    future = opts[opts['exp_dt'] >= '2026-05-01'].sort_values('exp_dt')
    if len(future) == 0:
        future = opts.sort_values('exp_dt', ascending=False).head(20)

    print(f"\n{idx_name}: testing with nearest available contract")
    if len(future) > 0:
        # Find ATM-ish: pick mid strike
        strikes = sorted(future['SEM_STRIKE_PRICE'].unique())
        mid_strike = strikes[len(strikes)//2] if strikes else None
        sample_row = future[future['SEM_STRIKE_PRICE'] == mid_strike].iloc[0] if mid_strike else future.iloc[0]
        sec_id = str(int(sample_row['SEM_SMST_SECURITY_ID']))
        expiry_code = sample_row.get('SEM_EXPIRY_CODE', 0)
        print(f"  Contract: {sample_row['SEM_TRADING_SYMBOL']} | sec_id={sec_id} | expiry_code={expiry_code}")
        
        # Test 1: historical_daily_data with NSE_FNO
        for from_d, to_d in [('2025-02-03', '2025-03-05'), ('2026-03-01', '2026-04-30')]:
            try:
                resp = dhan.historical_daily_data(
                    security_id=sec_id,
                    exchange_segment=exch,
                    instrument_type='OPTIDX',
                    from_date=from_d,
                    to_date=to_d,
                    expiry_code=int(expiry_code) if pd.notna(expiry_code) else 0
                )
                status = resp.get('status')
                data = resp.get('data', {})
                if isinstance(data, dict):
                    n = len(data.get('timestamp', []))
                else:
                    n = len(data) if data else 0
                print(f"  historical_daily [{from_d}→{to_d}]: status={status}, rows={n}")
                if n > 0:
                    print(f"  WORKS! Sample: {list(data.items())[:3] if isinstance(data, dict) else data[:2]}")
            except Exception as e:
                print(f"  historical_daily [{from_d}→{to_d}]: ERROR {e}")
            time.sleep(0.5)
        
        # Test 2: intraday_minute_data
        try:
            resp = dhan.intraday_minute_data(
                security_id=sec_id,
                exchange_segment=exch,
                instrument_type='OPTIDX',
                interval=1,
                from_date='2026-03-01',
                to_date='2026-03-07'
            )
            status = resp.get('status')
            data = resp.get('data', {})
            if isinstance(data, dict):
                n = len(data.get('timestamp', []))
            else:
                n = len(data) if data else 0
            print(f"  intraday_minute [2026-03]: status={status}, rows={n}")
            if n > 0:
                print(f"  SUCCESS! This works for {idx_name}!")
        except Exception as e:
            print(f"  intraday_minute: ERROR {e}")
        time.sleep(0.5)

print("\n" + "="*70)
print("PROBE: Use same approach as NIFTY — fetch via expiry rolling option")
print("  NIFTY uses sec_id=13 (the INDEX itself) with instrument_type=INDEX")
print("  for spot data, but for OPTIONS it uses the actual contract sec_id")
print("  Let's check what sec_id the actual working NIFTY parquets used")
print("="*70)

# Read one existing NIFTY parquet
import glob
pqs = sorted(glob.glob('data/raw/NIFTY_expired_2025-02-03_2025-03-05_ATM_CALL_1min_MONTH_1.parquet'))
if pqs:
    pq = pd.read_parquet(pqs[0])
    print(f"NIFTY parquet columns: {list(pq.columns)}")
    print(f"Sample: {pq.iloc[100].to_dict()}")
    print(f"spot range: {pq['spot'].min():.0f} to {pq['spot'].max():.0f}")
    print(f"close range: {pq['close'].min():.2f} to {pq['close'].max():.2f}")
    print(f"oi range: {pq['oi'].min():.0f} to {pq['oi'].max():.0f}")
