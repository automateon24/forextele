import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\dashboard_server.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()
print("=== Search for completed trades rendering in UI ===")
for idx, line in enumerate(lines):
    if idx >= 866:
        if any(x in line for x in ["completed_trades", "win", "loss", "stats", "pnl"]):
            print(f"  Line {idx+1}: {line.strip()}")
