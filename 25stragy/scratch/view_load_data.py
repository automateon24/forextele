import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\BACKTEST_V7_MULTIINDEX.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()
print("=== Lines 150 to 220 ===")
for i in range(149, min(220, len(lines))):
    print(f"  Line {i+1}: {lines[i]}")
