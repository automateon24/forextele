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
    "securityId": "79738",
    "exchangeSegment": "NSE_FNO",
    "instrument": "OPTIDX",
    "fromDate": "2026-06-25",
    "toDate": "2026-06-25",
    "interval": "1"
}

r = requests.post(f"{BASE_URL}/charts/intraday", json=payload, headers=HEADERS, timeout=30)
print("Status Code:", r.status_code)
resp = r.json()
print("Response Status:", resp.get("status") if isinstance(resp, dict) else "Non-dict response")
if isinstance(resp, dict) and resp.get("status") == "success":
    data = resp.get("data", {})
    if "data" in data:
        data = data["data"]
    timestamps = data.get("timestamp", [])
    print("Fetched", len(timestamps), "candles for option 79738 on June 25!")
else:
    print("Response:", str(resp)[:300])
