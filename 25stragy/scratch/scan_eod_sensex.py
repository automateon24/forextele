import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\data\daily_analysis_20260625.log"
if os.path.exists(path):
    print("=== Scanning EOD Analysis Log for SENSEX ===")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if "SENSEX" in line or "sensex" in line.lower():
                print(line.strip())
else:
    print("daily_analysis_20260625.log does not exist!")
