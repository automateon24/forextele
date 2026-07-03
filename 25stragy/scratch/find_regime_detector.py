import os

base_dir = r"C:\cursor\options\niftyopt"
v15_path = os.path.join(base_dir, "LIVE_PORTFOLIO_TRADER.py")

with open(v15_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== RegimeDetector in V15 ===")
for idx, line in enumerate(lines):
    if "class RegimeDetector" in line:
        print(f"Found RegimeDetector starting at line {idx+1}")
        # Print 50 lines
        for j in range(idx, min(len(lines), idx+60)):
            print(f"{j+1}: {lines[j].strip()}")
        break
