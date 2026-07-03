import os

base_dir = r"C:\cursor\options\niftyopt"
v15_path = os.path.join(base_dir, "LIVE_PORTFOLIO_TRADER.py")

with open(v15_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== Search for RegimeDetector imports/references in V15 ===")
for idx, line in enumerate(lines):
    if "RegimeDetector" in line:
        print(f"{idx+1}: {line.strip()}")
