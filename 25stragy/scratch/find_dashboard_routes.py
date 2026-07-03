import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\dashboard_server.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print("=== Search for routes and rendering ===")
for idx, line in enumerate(content.splitlines()):
    if "@app.get" in line or "HTMLResponse" in line or "template" in line or "def get" in line:
        print(f"  Line {idx+1}: {line.strip()}")
