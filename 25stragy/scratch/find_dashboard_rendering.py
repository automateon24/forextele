import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\dashboard_server.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print("=== Search for rendering/win_rate logic in dashboard_server.py ===")
for idx, line in enumerate(content.splitlines()):
    if any(x in line.lower() for x in ["win_rate", "percentage", "winrate", "ratio"]):
        print(f"  Line {idx+1}: {line.strip()}")
