import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\LIVE_PORTFOLIO_TRADER.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()
print("=== Save lines in LIVE_PORTFOLIO_TRADER.py ===")
for idx, line in enumerate(lines):
    if "to_csv" in line or "to_parquet" in line:
        print(f"  Line {idx+1}: {line.strip()}")
        # print next 3 lines
        for i in range(idx+1, min(len(lines), idx+4)):
            print(f"    {lines[i].strip()}")
