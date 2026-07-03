import sys, os, json
sys.path.insert(0, r'c:\cursor\options\niftyopt\Lib\site-packages')
from dhanhq import dhanhq

TOKEN_FILE = r'C:\cursor\options\niftyopt\config\dhan_tokens.json'
CLIENT_ID  = '1101936133'

with open(TOKEN_FILE) as f:
    t = json.load(f)
client = dhanhq(CLIENT_ID, t['access_token'])

for exch in ['IDX_I', 'BSE_I']:
    print(f"Testing SENSEX (51) with exchange={exch}...")
    try:
        r = client.expiry_list(under_security_id=51, under_exchange_segment=exch)
        print(f"  Result: {r.get('status')}, data: {r.get('data')}")
    except Exception as e:
        print(f"  Error: {e}")
