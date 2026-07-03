import os
import difflib

root_path = r"C:\cursor\options\niftyopt\LIVE_PORTFOLIO_TRADER.py"
sub_path = r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v15.py"

with open(root_path, "r", encoding="utf-8") as f:
    root_lines = f.readlines()
with open(sub_path, "r", encoding="utf-8") as f:
    sub_lines = f.readlines()

diff = difflib.ndiff(root_lines, sub_lines)
diff_lines = [line for line in diff if line.startswith('- ') or line.startswith('+ ')]

print(f"Total diff lines: {len(diff_lines)}")
print("=== Sample of Differences (first 40 lines) ===")
for line in diff_lines[:40]:
    print(line.strip())
