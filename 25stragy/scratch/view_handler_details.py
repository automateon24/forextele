import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\src\module1_data\dhan_handler.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.read().splitlines()

print("=== Lines 298 to 330 ===")
for i in range(297, min(330, len(lines))):
    print(f"  Line {i+1}: {lines[i]}")
