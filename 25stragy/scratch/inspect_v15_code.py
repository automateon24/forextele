import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\cursor\options\niftyopt"
v15_path = os.path.join(base_dir, "LIVE_PORTFOLIO_TRADER.py")

with open(v15_path, "r", encoding="utf-8") as f:
    content = f.read()

print("=== Strike/Contract Selection in V15 ===")
# Search for get_option or select or strike or delta or greeks in V15
import re
for m in re.finditer(r"def\s+select|def\s+get_option|strike_selection|atm_strike|Greeks", content, re.IGNORECASE):
    start = max(0, m.start() - 150)
    end = min(len(content), m.end() + 150)
    print(f"--- MATCH ---\n{content[start:end]}\n")
