import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\LIVE_PORTFOLIO_TRADER.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print("=== References to active_trades ===")
for idx, line in enumerate(content.splitlines()):
    if "active_trades" in line:
        if not line.strip().startswith("#"):
            print(f"  Line {idx+1}: {line.strip()}")
