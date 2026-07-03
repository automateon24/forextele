import os
import re

log_path = r"C:\cursor\options\niftyopt\data\live_portfolio_trader.log"
if not os.path.exists(log_path):
    print("Log file does not exist!")
    sys.exit(0)

print("=== Scanning Log for Capital Constraints ===")
with open(log_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

count = 0
for idx, line in enumerate(lines):
    if "skipped due to capital constraint" in line:
        count += 1
        if count <= 15:
            print(f"Line {idx+1}: {line.strip()}")

print(f"Total capital constraint warnings: {count}")
