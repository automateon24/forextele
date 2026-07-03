import sys
import json
sys.path.insert(0, r'C:\cursor\options\niftyopt')
sys.path.insert(0, r'C:\cursor\options\niftyopt\Lib\site-packages')
from dhanhq import dhanhq

with open(r'C:\cursor\options\niftyopt\config\dhan_tokens.json', 'r') as f:
    tokens = json.load(f)
access_token = tokens.get('access_token')

client = dhanhq("1101936133", access_token)
securities = {
    'IDX_I': [13, 25, 27, 51, 442]
}
r = client.ticker_data(securities=securities)
print(json.dumps(r, indent=2))
