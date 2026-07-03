import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\dashboard_server.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()
print("=== API Endpoints ===")
for idx, line in enumerate(lines):
    if "@app.get" in line:
        print(f"  Line {idx+1}: {line.strip()}")
        # print next 5 lines
        for i in range(idx+1, min(len(lines), idx+6)):
            print(f"    {lines[i].strip()}")
