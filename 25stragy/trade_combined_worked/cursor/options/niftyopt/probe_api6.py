#!/usr/bin/env python3
"""
Find correct security IDs for BN/FN/SENSEX options and test actual data fetch.
"""
import json, time, os, glob
import pandas as pd

with open('config/dhan_tokens.json') as f:
    token = json.load(f)['access_token']
from dhanhq import dhanhq
dhan = dhanhq('1101936133', token)

df_sec = pd.read_csv('backtest_real_data/dhan_security_master.csv', low_memory=False)
print(f"Security master: {len(df_sec)} rows")

# ── What expiry dates are in the security master? ─────────────────────────────
print("\n" + "="*70)
print("STEP 1: Expiry dates in security master per index")
print("="*70)
for idx_name, prefix in [('NIFTY','NIFTY-'), ('BANKNIFTY','BANKNIFTY-'), ('FINNIFTY','FINNIFTY-'), ('SENSEX','SENSEX-')]:
    mask = (df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith(prefix) &
            (df_sec['SEM_INSTRUMENT_NAME'].astype(str) == 'OPTIDX'))
    opts = df_sec[mask].copy()
    if len(opts) == 0:
        # Fallback to any OPT
        mask2 = (df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith(prefix) &
                 df_sec['SEM_INSTRUMENT_NAME'].astype(str).str.contains('OPT', na=False))
        opts = df_sec[mask2].copy()
    opts['exp_dt'] = pd.to_datetime(opts['SEM_EXPIRY_DATE'], errors='coerce')
    expiries = sorted(opts['exp_dt'].dropna().unique())
    if expiries:
        print(f"  {idx_name}: {len(opts)} contracts | {expiries[0].date()} → {expiries[-1].date()}")
        print(f"    First 3: {[str(e.date()) for e in expiries[:3]]}")
        print(f"    Last 3:  {[str(e.date()) for e in expiries[-3:]]}")
    else:
        print(f"  {idx_name}: NO contracts found")

# ── Read an existing NIFTY parquet to see what columns look like ──────────────
print("\n" + "="*70)
print("STEP 2: Existing NIFTY option parquet structure")
print("="*70)
pqs = sorted(glob.glob('data/raw/NIFTY_expired_2025-02-03_2025-03-05_ATM_CALL_1min_MONTH_1.parquet'))
if pqs:
    pq = pd.read_parquet(pqs[0])
    print(f"Columns: {list(pq.columns)}")
    print(f"Rows: {len(pq)}")
    print(f"Sample row:\n{pq.iloc[100].to_dict()}")
else:
    # any NIFTY parquet
    pqs = sorted(glob.glob('data/raw/NIFTY_expired_2025*ATM_CALL*.parquet'))
    if pqs:
        pq = pd.read_parquet(pqs[0])
        print(f"File: {pqs[0]}")
        print(f"Columns: {list(pq.columns)}")
        print(f"Sample: {pq.iloc[0].to_dict()}")
    else:
        print("No NIFTY option parquets found")

# ── Now test actual fetch for BN/FN/SENSEX using security IDs ─────────────────
print("\n" + "="*70)
print("STEP 3: Test fetching option 1-min data for BN/FN/SENSEX")
print("="*70)

# Map index to (prefix, spot_sec_id, exchange_segment)
TARGETS = [
    ('BANKNIFTY', 'BANKNIFTY-', '25',  'NSE_FNO'),
    ('FINNIFTY',  'FINNIFTY-',  '27',  'NSE_FNO'),
    ('SENSEX',    'SENSEX-',    '51',  'BSE_FNO'),
]

SEGMENT_MAP = {'D': 'NSE_FNO', 'B': 'BSE_FNO'}

for idx_name, prefix, spot_id, default_exch in TARGETS:
    print(f"\n--- {idx_name} ---")

    mask = (df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith(prefix) &
            (df_sec['SEM_INSTRUMENT_NAME'].astype(str) == 'OPTIDX'))
    opts = df_sec[mask].copy()
    if len(opts) == 0:
        mask2 = (df_sec['SEM_TRADING_SYMBOL'].astype(str).str.startswith(prefix) &
                 df_sec['SEM_INSTRUMENT_NAME'].astype(str).str.contains('OPT', na=False))
        opts = df_sec[mask2].copy()
    if len(opts) == 0:
        print(f"  No contracts in security master for {idx_name}")
        continue

    opts['exp_dt'] = pd.to_datetime(opts['SEM_EXPIRY_DATE'], errors='coerce')

    # Use contracts with the most recent expiry available
    latest_opts = opts.sort_values('exp_dt', ascending=False).head(50)
    # Pick mid-strike contract (near ATM)
    strikes = sorted(latest_opts['SEM_STRIKE_PRICE'].dropna().unique())
    mid_idx = len(strikes) // 2
    mid_strike = strikes[mid_idx] if strikes else None

    sample = latest_opts[latest_opts['SEM_STRIKE_PRICE'] == mid_strike].iloc[0] if mid_strike else latest_opts.iloc[0]
    sec_id = str(int(sample['SEM_SMST_SECURITY_ID']))
    seg = str(sample['SEM_SEGMENT'])
    exch_seg = SEGMENT_MAP.get(seg, default_exch)
    exp_code = sample.get('SEM_EXPIRY_CODE', 0)
    exp_date = sample['SEM_EXPIRY_DATE']

    print(f"  Contract: {sample['SEM_TRADING_SYMBOL']}")
    print(f"  sec_id={sec_id}, segment={seg}→{exch_seg}, expiry={exp_date}, code={exp_code}")

    # Fetch date range: use expiry month - 1 month before expiry
    try:
        exp_dt = pd.to_datetime(exp_date)
        fetch_start = (exp_dt - pd.DateOffset(months=1)).strftime('%Y-%m-%d')
        fetch_end   = exp_dt.strftime('%Y-%m-%d')
    except Exception:
        fetch_start = '2026-03-01'
        fetch_end   = '2026-04-30'

    # Test 1: intraday_minute_data
    for inst in ['OPTIDX', 'OPTIONS']:
        try:
            resp = dhan.intraday_minute_data(
                security_id=sec_id,
                exchange_segment=exch_seg,
                instrument_type=inst,
                interval=1,
                from_date=fetch_start,
                to_date=fetch_end
            )
            status = resp.get('status', 'unknown')
            data = resp.get('data', {})
            n = len(data.get('timestamp', [])) if isinstance(data, dict) else len(data or [])
            print(f"  intraday_minute (inst={inst}, {fetch_start}→{fetch_end}): status={status}, rows={n}")
            if n > 0:
                ts = data['timestamp']
                print(f"  ✅ SUCCESS! First bar ts={ts[0]}, close={data['close'][0]}")
                break
        except Exception as e:
            print(f"  intraday_minute (inst={inst}): ERROR {e}")
        time.sleep(0.3)

    # Test 2: historical_daily_data
    for inst in ['OPTIDX']:
        for exp_c in [int(exp_code) if pd.notna(exp_code) else 0, 0, 1]:
            try:
                resp = dhan.historical_daily_data(
                    security_id=sec_id,
                    exchange_segment=exch_seg,
                    instrument_type=inst,
                    from_date=fetch_start,
                    to_date=fetch_end,
                    expiry_code=exp_c
                )
                status = resp.get('status', 'unknown')
                data = resp.get('data', {})
                n = len(data.get('timestamp', [])) if isinstance(data, dict) else len(data or [])
                print(f"  historical_daily (inst={inst}, exp_code={exp_c}): status={status}, rows={n}")
                if n > 0:
                    print(f"  ✅ SUCCESS! First={data['timestamp'][0]}, close={data['close'][0]}")
                    break
            except Exception as e:
                print(f"  historical_daily (inst={inst}, exp_code={exp_c}): ERROR {e}")
            time.sleep(0.3)

    time.sleep(0.5)

print("\n" + "="*70)
print("STEP 4: Try fetching BN/FN spot as OPTIDX rolling (same as NIFTY rolling option approach)")
print("="*70)
# NIFTY rolling option fetch uses expiry_code parameter — let's check what values work
for idx_name, sec_id, exch in [('BANKNIFTY','25','NSE_FNO'), ('FINNIFTY','27','NSE_FNO'), ('SENSEX','51','BSE_FNO')]:
    print(f"\n{idx_name} rolling option test:")
    for exp_code in [0, 1, 2, 3]:
        try:
            resp = dhan.historical_daily_data(
                security_id=sec_id,
                exchange_segment=exch,
                instrument_type='OPTIDX',
                from_date='2025-02-03',
                to_date='2025-03-05',
                expiry_code=exp_code
            )
            status = resp.get('status', 'unknown')
            data = resp.get('data', {})
            n = len(data.get('timestamp', [])) if isinstance(data, dict) else len(data or [])
            print(f"  sec={sec_id}, exch={exch}, exp_code={exp_code}: {status}, rows={n}")
            if n > 0:
                print(f"  ✅ WORKS! close sample={data['close'][:3]}")
        except Exception as e:
            print(f"  exp_code={exp_code}: ERROR {e}")
        time.sleep(0.3)
