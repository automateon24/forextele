import sys, os, json
from datetime import datetime, timedelta
sys.path.insert(0, r'c:\cursor\options\niftyopt\Lib\site-packages')
from dhanhq import dhanhq

TOKEN_FILE = r'C:\cursor\options\niftyopt\config\dhan_tokens.json'
CLIENT_ID  = '1101936133'

with open(TOKEN_FILE) as f:
    t = json.load(f)
client = dhanhq(CLIENT_ID, t['access_token'])

today = datetime.now()
start_date = (today - timedelta(days=4)).strftime('%Y-%m-%d')
end_date = today.strftime('%Y-%m-%d')

INDICES = [
    ('NIFTY', '13'),
    ('BANKNIFTY', '25'),
    ('FINNIFTY', '27'),
    ('MIDCPNIFTY', '442'),
    ('SENSEX', '51')
]

for name, sec_id in INDICES:
    print(f"Fetching {name} ({sec_id}) from {start_date} to {end_date}...")
    try:
        r = client.intraday_minute_data(
            security_id=sec_id,
            exchange_segment='IDX_I',
            instrument_type='INDEX',
            from_date=start_date,
            to_date=end_date,
            interval=1
        )
        if r and r.get('status') == 'success':
            closes = r.get('data', {}).get('close', [])
            print(f"  Success! Fetched {len(closes)} candles. Closes tail: {closes[-5:]}")
        else:
            print(f"  Failed: {r}")
    except Exception as e:
        print(f"  Error: {e}")
