import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\src\module1_data\data_loader.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.read().splitlines()

print("=== get_historical_data_1min usage in data_loader.py ===")
for idx, line in enumerate(lines):
    if "get_historical_data_1min" in line:
        print(f"  Line {idx+1}: {line.strip()}")
        # Print next 5 lines
        for i in range(idx+1, min(len(lines), idx+6)):
            print(f"    {lines[i].strip()}")
