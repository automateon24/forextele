import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\BACKTEST_V7_MULTIINDEX.py"
with open(path, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if "def load_option_data" in line:
            print(f"Line {idx+1}: {line.strip()}")
