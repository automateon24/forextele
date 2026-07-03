#!/usr/bin/env python3
"""
Test POST /v2/charts/rollingoption for BANKNIFTY, FINNIFTY, MIDCPNIFTY, SENSEX.
This is the SAME endpoint that successfully fetched all NIFTY 1-min option data.
"""
import json, time, requests
import pandas as pd

with open('config/dhan_tokens.json') as f:
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

# Index configs: (name, securityId, exchangeSegment, atm_step)
INDICES = [
    ('NIFTY',       13,   'NSE_FNO', 50),    # baseline — should work
    ('BANKNIFTY',   25,   'NSE_FNO', 100),
    ('FINNIFTY',    27,   'NSE_FNO', 50),
    ('MIDCPNIFTY',  442,  'NSE_FNO', 25),
    ('SENSEX',      51,   'BSE_FNO', 100),
]

TEST_PERIOD = ('2025-02-03', '2025-03-05')
TEST_STRIKE = 'ATM'

print("="*70)
print("TEST: POST /v2/charts/rollingoption for each index")
print(f"  Period: {TEST_PERIOD[0]} → {TEST_PERIOD[1]}, Strike: {TEST_STRIKE}, CALL")
print("="*70)

working = []

for idx_name, sec_id, exch_seg, atm_step in INDICES:
    print(f"\n--- {idx_name} (securityId={sec_id}, exchange={exch_seg}) ---")

    # Try different expiry_flag and expiry_code combos
    for exp_flag, exp_code in [('MONTH', 1), ('MONTH', 0), ('WEEK', 1), ('WEEK', 0)]:
        payload = {
            "exchangeSegment": exch_seg,
            "interval": "1",
            "securityId": sec_id,
            "instrument": "OPTIDX",
            "expiryFlag": exp_flag,
            "expiryCode": exp_code,
            "strike": TEST_STRIKE,
            "drvOptionType": "CALL",
            "requiredData": ["open", "high", "low", "close", "iv", "volume", "oi", "spot"],
            "fromDate": TEST_PERIOD[0],
            "toDate": TEST_PERIOD[1]
        }
        try:
            r = requests.post(f"{BASE_URL}/charts/rollingoption",
                              json=payload, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                resp = r.json()
                outer = resp.get('data', {})
                if outer:
                    # Try ce/pe sub-keys
                    data = outer.get('ce') or outer.get('pe') or outer
                    ts = data.get('timestamp', []) if isinstance(data, dict) else []
                    n = len(ts)
                    if n > 0:
                        first_ts = pd.to_datetime(ts[0], unit='s', utc=True).tz_convert('Asia/Kolkata')
                        last_ts  = pd.to_datetime(ts[-1], unit='s', utc=True).tz_convert('Asia/Kolkata')
                        close = data.get('close', [])
                        spot  = data.get('spot', [])
                        print(f"  ✅ flag={exp_flag}, code={exp_code}: {n} bars")
                        print(f"     range: {first_ts} → {last_ts}")
                        print(f"     close: {close[:3]}  spot: {spot[:3]}")
                        working.append({'name': idx_name, 'sec_id': sec_id, 'exch': exch_seg,
                                        'exp_flag': exp_flag, 'exp_code': exp_code, 'n_bars': n})
                        break
                    else:
                        print(f"  flag={exp_flag}, code={exp_code}: 200 but empty data, keys={list(outer.keys()) if isinstance(outer, dict) else type(outer)}")
                else:
                    print(f"  flag={exp_flag}, code={exp_code}: 200 but data=None, resp={str(resp)[:100]}")
            else:
                print(f"  flag={exp_flag}, code={exp_code}: HTTP {r.status_code} — {r.text[:100]}")
        except Exception as e:
            print(f"  flag={exp_flag}, code={exp_code}: EXCEPTION {e}")
        time.sleep(0.4)

print("\n" + "="*70)
print("SUMMARY — Working combinations:")
print("="*70)
for w in working:
    print(f"  {w['name']}: sec_id={w['sec_id']}, exch={w['exch']}, "
          f"exp_flag={w['exp_flag']}, exp_code={w['exp_code']}, bars={w['n_bars']}")

if not working:
    print("  NONE worked yet — trying alternative approaches below...")

    # Try: maybe SENSEX uses BSE_FNO with different securityId
    print("\n  Trying SENSEX with alternative sec IDs...")
    for alt_id in [1, 2, 16, 51, 272, 999001]:
        payload = {
            "exchangeSegment": "BSE_FNO",
            "interval": "1",
            "securityId": alt_id,
            "instrument": "OPTIDX",
            "expiryFlag": "MONTH",
            "expiryCode": 1,
            "strike": "ATM",
            "drvOptionType": "CALL",
            "requiredData": ["open","high","low","close","spot"],
            "fromDate": "2025-02-03",
            "toDate": "2025-03-05"
        }
        try:
            r = requests.post(f"{BASE_URL}/charts/rollingoption",
                              json=payload, headers=HEADERS, timeout=10)
            data = r.json().get('data', {})
            if data:
                sub = data.get('ce') or data.get('pe') or data
                n = len(sub.get('timestamp', [])) if isinstance(sub, dict) else 0
                if n > 0:
                    print(f"  ✅ SENSEX alt sec_id={alt_id}: {n} bars!")
                else:
                    print(f"  sec_id={alt_id}: 200 but empty")
            else:
                print(f"  sec_id={alt_id}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  sec_id={alt_id}: {e}")
        time.sleep(0.3)
