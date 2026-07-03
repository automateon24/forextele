import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\dashboard_server.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()
print("=== Lines 1080 to 1115 ===")
for i in range(1079, min(1115, len(lines))):
    print(f"  Line {i+1}: {lines[i]}")
