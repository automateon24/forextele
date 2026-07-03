import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\LIVE_PORTFOLIO_TRADER.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

for term in ["lot_multiplier", "max_test_lots"]:
    print(f"=== Occurrences of '{term}' ===")
    for idx, line in enumerate(content.splitlines()):
        if term in line:
            print(f"  Line {idx+1}: {line.strip()}")
