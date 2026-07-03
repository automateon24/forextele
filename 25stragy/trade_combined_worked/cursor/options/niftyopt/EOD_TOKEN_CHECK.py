import json
import datetime

try:
    with open('config/dhan_tokens.json') as f:
        t = json.load(f)
    exp = t.get('expiry_time', 'Unknown')
    now = datetime.datetime.now().isoformat()
    status = 'VALID' if exp > now else 'EXPIRED - RUN TOKEN REFRESH NOW'
    print(f'  Token expires : {exp}')
    print(f'  Status        : {status}')
except Exception as e:
    print(f'  ERROR reading token file: {e}')
