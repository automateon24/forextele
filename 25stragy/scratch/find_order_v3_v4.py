import os
import sys

# Reconfigure stdout to use utf-8
sys.stdout.reconfigure(encoding='utf-8')

root_dir = r"C:\cursor\options\niftyopt"
files = ["MODULAR_TRADER_V3.py", "MODULAR_TRADER_V4.py"]

for f_name in files:
    path = os.path.join(root_dir, f_name)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"=== Order References in {f_name} ===")
    for idx, line in enumerate(content.splitlines()):
        if any(x in line.lower() for x in ["place_order", "dhan.place", "submit", "paper", "simulation"]):
            if not line.strip().startswith("#"):
                print(f"  Line {idx+1}: {line.strip()}")
