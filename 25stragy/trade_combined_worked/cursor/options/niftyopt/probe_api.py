#!/usr/bin/env python3
"""Probe Dhan API to find what actual options data is available for all indices."""
import json, time
with open('config/dhan_tokens.json') as f:
    token = json.load(f)['access_token']
from dhanhq import dhanhq
dhan = dhanhq('1101936133', token)

INDICES = [
    ('NIFTY',      '13',  'IDX_I'),
    ('BANKNIFTY',  '25',  'IDX_I'),
    ('FINNIFTY',   '27',  'IDX_I'),
    ('MIDCPNIFTY', '442', 'IDX_I'),
    ('SENSEX',     '51',  'BSE_I'),
]

print("="*70)
print("PROBE: expiry_list for each index")
print("="*70)
for name, sec_id, exch in INDICES:
    try:
        r = dhan.expiry_list(sec_id, exch)
        expiries = r.get('data', {}).get('expiry', [])
        print(f"  {name}: {len(expiries)} expiries — first 5: {expiries[:5]}")
    except Exception as e:
        print(f"  {name}: ERROR — {e}")
    time.sleep(0.5)

print("\n" + "="*70)
print("PROBE: option_chain for each index (latest expiry)")
print("="*70)
for name, sec_id, exch in INDICES:
    try:
        r = dhan.expiry_list(sec_id, exch)
        expiries = r.get('data', {}).get('expiry', [])
        if not expiries:
            print(f"  {name}: no expiries found")
            continue
        latest_exp = expiries[0]
        oc = dhan.option_chain(sec_id, exch, latest_exp)
        status = oc.get('status')
        data = oc.get('data', {})
        # Show structure
        if isinstance(data, dict):
            keys = list(data.keys())
            print(f"  {name} expiry={latest_exp}: status={status}, keys={keys[:8]}")
            if 'optionChain' in data:
                oc_data = data['optionChain']
                print(f"    optionChain type={type(oc_data)}, len={len(oc_data) if oc_data else 0}")
                if oc_data:
                    first = oc_data[0] if isinstance(oc_data, list) else list(oc_data.items())[0]
                    print(f"    first entry: {str(first)[:200]}")
        elif isinstance(data, list):
            print(f"  {name}: list of {len(data)} — first: {str(data[0])[:150] if data else 'empty'}")
        else:
            print(f"  {name}: data type={type(data)}")
    except Exception as e:
        print(f"  {name}: ERROR — {e}")
    time.sleep(1.0)

print("\n" + "="*70)
print("PROBE: historical_daily_data for options (FNO segment)")
print("  Testing if we can fetch historical data for a specific option contract")
print("="*70)

# NIFTY option security IDs from security master
# Let's try fetching for NSE_FNO segment which has option contracts
test_cases = [
    ('NIFTY 25000 CE', 'NSE_FNO', '15H02', '2025-02-01', '2025-02-28'),
    ('BANKNIFTY_FNO',  'NSE_FNO', '25',    '2025-02-01', '2025-02-28'),
]
for label, seg, sec, fd, td in test_cases:
    try:
        r = dhan.historical_daily_data(
            security_id=sec, exchange_segment=seg,
            instrument_type='OPTIDX', from_date=fd, to_date=td
        )
        print(f"  {label}: status={r.get('status')}, rows={len(r.get('data',[]))}")
    except Exception as e:
        print(f"  {label}: {e}")
    time.sleep(0.5)

print("\n" + "="*70)
print("PROBE: fetch_security_list to find option security IDs")
print("="*70)
for exch in ['NSE_FNO', 'BSE_FNO']:
    try:
        r = dhan.fetch_security_list(exch)
        print(f"  {exch}: type={type(r)}, len={len(r) if r else 0}")
        if r and len(r) > 0:
            print(f"  First entry: {str(r[0])[:300]}")
    except Exception as e:
        print(f"  {exch}: {e}")
    time.sleep(0.5)
