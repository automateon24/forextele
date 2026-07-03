import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\dashboard_server.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()
print("=== Search for port or uvicorn ===")
for idx, line in enumerate(lines):
    if "port" in line.lower() or "uvicorn.run" in line:
        print(f"  Line {idx+1}: {line.strip()}")
