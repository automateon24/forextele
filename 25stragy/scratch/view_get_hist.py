import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\src\module1_data\dhan_handler.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.read().splitlines()

for idx, line in enumerate(lines):
    if "def get_historical_data_1min" in line:
        print("=== Implementation of get_historical_data_1min ===")
        for i in range(idx, min(len(lines), idx+40)):
            print(f"  Line {i+1}: {lines[i]}")
        break
