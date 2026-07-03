import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\cursor\options\niftyopt"
v15_path = os.path.join(base_dir, "LIVE_PORTFOLIO_TRADER.py")

with open(v15_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== Search for Option Selection helpers in V15 ===")
for idx, line in enumerate(lines):
    line_lower = line.lower()
    if "def " in line_lower and any(x in line_lower for x in ["option", "strike", "contract", "closest", "select"]):
        print(f"{idx+1}: {line.strip()}")
        # print next 20 lines
        for j in range(idx+1, min(len(lines), idx+25)):
            print(f"  {j+1}: {lines[j].strip()}")
