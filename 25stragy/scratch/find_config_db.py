import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\LIVE_PORTFOLIO_TRADER.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print("=== config_db References ===")
for idx, line in enumerate(content.splitlines()):
    if "config_db" in line:
        print(f"  Line {idx+1}: {line.strip()}")
