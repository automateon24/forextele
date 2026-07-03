import sys, os, json, time
sys.path.insert(0, r'c:\cursor\options\niftyopt\Lib\site-packages')
from dhanhq import dhanhq

TOKEN_FILE = r'C:\cursor\options\niftyopt\config\dhan_tokens.json'
CLIENT_ID  = '1101936133'

with open(TOKEN_FILE) as f:
    t = json.load(f)
client = dhanhq(CLIENT_ID, t['access_token'])

INDICES = [
    ('NIFTY', '13'),
    ('BANKNIFTY', '25'),
    ('FINNIFTY', '27'),
    ('MIDCPNIFTY', '442'),
    ('SENSEX', '51')
]

for name, sec_id in INDICES:
    print(f"Fetching option chain for {name} ({sec_id})...")
    try:
        r = client.expiry_list(under_security_id=int(sec_id), under_exchange_segment='IDX_I')
        if r and r.get('status') == 'success':
            data_dict = r.get('data', {})
            expiries = []
            if isinstance(data_dict, dict):
                expiries = data_dict.get('data', [])
            else:
                expiries = data_dict
            
            if not expiries:
                print(f"  No expiries found: {r}")
                continue
            first_expiry = expiries[0]
            print(f"  First expiry: {first_expiry}. Fetching chain...")
            oc = client.option_chain(under_security_id=int(sec_id), under_exchange_segment='IDX_I', expiry=first_expiry)
            if oc and oc.get('status') == 'success':
                oc_data = oc.get('data', {})
                nested_oc = {}
                if isinstance(oc_data, dict):
                    if 'oc' in oc_data:
                        nested_oc = oc_data['oc']
                    elif 'data' in oc_data:
                        nested_oc = oc_data['data'].get('oc', {})
                print(f"  Success! Fetched {len(nested_oc)} strikes. Sample keys: {list(nested_oc.keys())[:3]}")
            else:
                print(f"  Failed option chain: {oc}")
        else:
            print(f"  Failed expiry list: {r}")
    except Exception as e:
        print(f"  Error: {e}")
    time.sleep(1.0)
