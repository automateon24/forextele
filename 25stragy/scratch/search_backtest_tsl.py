import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\25stragy\BACKTEST_V15_HYBRID_AGGRESSIVE.py"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.read().splitlines()

print(f"=== Search for trailing SL in {path} ===")
count = 0
for idx, line in enumerate(lines):
    if any(x in line.lower() for x in ["tsl", "trail", "activate"]):
        print(f"  Line {idx+1}: {line.strip()}")
        count += 1
        if count >= 30:
            print("  ... truncated ...")
            break
