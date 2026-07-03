import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\LIVE_PORTFOLIO_TRADER.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()
print("=== Search for Active Trade Check ===")
for idx, line in enumerate(lines):
    if any(x in line for x in ["active_trades", "already active", "is_active", "existing_trade"]):
        print(f"  Line {idx+1}: {line.strip()}")
