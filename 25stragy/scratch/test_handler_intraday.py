import sys
sys.path.insert(0, r"C:\cursor\options\niftyopt")
import json
from src.module1_data.dhan_handler import DhanDataHandler

# Load Dhan tokens
with open(r'c:\cursor\options\niftyopt\config\dhan_tokens.json') as f:
    creds = json.load(f)
TOKEN = creds['access_token']
CLIENT_ID = "1101936133"

handler = DhanDataHandler(CLIENT_ID, TOKEN)

print("Fetching NIFTY index intraday 1-min data using DhanDataHandler...")
df = handler.get_historical_data_1min(
    security_id="13",
    from_date="2026-06-25",
    to_date="2026-06-25",
    exchange_segment="IDX_LTP"
)
print("DataFrame Empty:", df.empty)
if not df.empty:
    print("DataFrame shape:", df.shape)
    print("First 3 rows:")
    print(df.head(3))
