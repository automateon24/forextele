import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

paths = [
    r"C:\cursor\options\niftyopt\MODULAR_TRADER_V3.py",
    r"C:\cursor\options\niftyopt\MODULAR_TRADER_V4.py",
    r"C:\cursor\options\niftyopt\MODULAR_TRADER_V15.py"
]

for p in paths:
    print(f"Path: {p} exists? {os.path.exists(p)}")
