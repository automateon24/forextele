import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v4.py"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.read().splitlines()

print(f"=== Adaptive References in {path} ===")
for idx, line in enumerate(lines):
    if "adaptive" in line.lower():
        print(f"  Line {idx+1}: {line.strip()}")
