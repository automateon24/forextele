import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\dashboard_server.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()
print("=== Search for Terminal Container ===")
for idx, line in enumerate(lines):
    if "Engine Audit Logs Terminal" in line:
        # print 20 lines before and after
        start = max(0, idx - 15)
        end = min(len(lines), idx + 20)
        for i in range(start, end):
            print(f"  Line {i+1}: {lines[i]}")
        break
