import sys
import json
import requests

# Read Dhan credentials
with open(r'c:\cursor\options\niftyopt\config\dhan_tokens.json') as f:
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

payload = {
    "exchangeSegment": "NSE_FNO",
    "interval": "1",
    "securityId": 13,
    "instrument": "OPTIDX",
    "expiryFlag": "MONTH",
    "expiryCode": 1,
    "strike": "ATM",
    "drvOptionType": "CALL",
    "requiredData": ["open", "high", "low", "close", "iv", "volume", "oi", "spot"],
    "fromDate": "2026-06-25",
    "toDate": "2026-06-25"
}

r = requests.post(f"{BASE_URL}/charts/rollingoption", json=payload, headers=HEADERS)
print("Status Code:", r.status_code)
print("Response text:")
print(r.text)
