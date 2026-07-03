import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

root_dir = r"C:\cursor\options\niftyopt"
files = ["MODULAR_TRADER_V3.py", "MODULAR_TRADER_V4.py"]

for f_name in files:
    path = os.path.join(root_dir, f_name)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"=== API Client Calls in {f_name} ===")
    for idx, line in enumerate(content.splitlines()):
        if ".place_" in line or ".order" in line or "dhan." in line:
            if not line.strip().startswith("#"):
                print(f"  Line {idx+1}: {line.strip()}")
