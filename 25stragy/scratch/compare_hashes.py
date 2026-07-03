import hashlib
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

def file_md5(path):
    if not os.path.exists(path):
        return None
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

pairs = [
    (r"C:\cursor\options\niftyopt\MODULAR_TRADER_V3.py", r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v3.py"),
    (r"C:\cursor\options\niftyopt\MODULAR_TRADER_V4.py", r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v4.py"),
]

for p1, p2 in pairs:
    md5_1 = file_md5(p1)
    md5_2 = file_md5(p2)
    print(f"MD5 comparison:")
    print(f"  {p1}: {md5_1}")
    print(f"  {p2}: {md5_2}")
    print(f"  Identical? {md5_1 == md5_2}")
