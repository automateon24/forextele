import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\united_Indian_market1.0\global_data_fetcher.py"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.read().splitlines()

for idx, line in enumerate(lines):
    if "def " in line:
        print(f"Line {idx+1}: {line.strip()}")
