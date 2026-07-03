import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\BACKTEST_V7_MULTIINDEX.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.read().splitlines()

print("=== Lines 318 to 360 ===")
for i in range(317, min(360, len(lines))):
    print(f"  Line {i+1}: {lines[i]}")
