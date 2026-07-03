import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\LIVE_PORTFOLIO_TRADER.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print("=== Capital Allocation & Sizing logic in LIVE_PORTFOLIO_TRADER.py ===")
for idx, line in enumerate(content.splitlines()):
    if any(x in line.lower() for x in ["capital", "avail", "skip", "constraint", "lot_size"]):
        if not line.strip().startswith("#"):
            print(f"  Line {idx+1}: {line.strip()}")
