import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\cursor\options\niftyopt"
v15_path = os.path.join(base_dir, "LIVE_PORTFOLIO_TRADER.py")

with open(v15_path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's search for trade entry functions or loop
matches = []
for m in re.finditer(r"def\s+execute_trade|def\s+check_strategy|def\s+run|def\s+enter_position|def\s+place_order", content, re.IGNORECASE):
    start = max(0, m.start() - 150)
    end = min(len(content), m.end() + 150)
    matches.append(f"--- MATCH ---\n{content[start:end]}\n")

print(f"Found {len(matches)} matches:")
for match in matches[:10]:
    print(match)
