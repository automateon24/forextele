import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\src\module1_data\dhan_handler.py"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.read().splitlines()

for idx, line in enumerate(lines):
    if "def " in line:
        print(f"Line {idx+1}: {line.strip()}")
