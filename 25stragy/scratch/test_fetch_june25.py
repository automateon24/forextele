import json
import requests
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Load Dhan tokens
with open(r'c:\cursor\options\niftyopt\config\dhan_tokens.json') as f:
    creds = json.load(f)
TOKEN = creds['access_token']
CLIENT_ID = "1101936133"
BASE_URL = "https://api.dhan.co/v2"
HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'access-token': TOKEN,
    'client-id': CLIENT_ID
}

payload = {
    "exchangeSegment": "NSE_FNO",
    "interval": "1",
    "securityId": 13, # NIFTY
    "instrument": "OPTIDX",
    "expiryFlag": "MONTH",
    "expiryCode": 1,
    "strike": "ATM",
    "drvOptionType": "CALL",
    "requiredData": ["open", "high", "low", "close", "iv", "volume", "oi", "spot"],
    "fromDate": "2026-05-20",
    "toDate": "2026-05-21"
}

r = requests.post(f"{BASE_URL}/charts/rollingoption", json=payload, headers=HEADERS, timeout=30)
print("Status Code:", r.status_code)
resp = r.json()
print("Response keys:", list(resp.keys()) if resp else "None")
if "data" in resp and resp["data"]:
    print("Data keys:", list(resp["data"].keys()))
    ce_data = resp["data"].get("ce", {}) or resp["data"]
    timestamps = ce_data.get("timestamp", [])
    print("Fetched", len(timestamps), "candles for June 25!")
else:
    print("Response remarks:", resp.get("remarks", "No remarks"))
