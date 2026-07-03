import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\BACKTEST_V7_MULTIINDEX.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()
print(f"=== Last 100 lines of {os.path.basename(path)} ===")
start = max(0, len(lines) - 100)
for i in range(start, len(lines)):
    print(f"  Line {i+1}: {lines[i]}")
