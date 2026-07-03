import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\dashboard_server.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print("=== Search for win rate / trade UI rendering ===")
lines = content.splitlines()
for idx, line in enumerate(lines):
    if idx >= 550:
        if any(x in line for x in ["Win Rate", "winRate", "percentage", "%", "totalTrades"]):
            print(f"  Line {idx+1}: {line.strip()}")
