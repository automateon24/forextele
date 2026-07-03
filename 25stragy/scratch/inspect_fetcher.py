import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\cursor\options\niftyopt"
fetcher_path = os.path.join(base_dir, "united_Indian_market1.0", "global_data_fetcher.py")

with open(fetcher_path, "r", encoding="utf-8") as f:
    content = f.read()

print("=== Warmup and Closes handling in GlobalDataFetcher ===")
# Search for performs warmup, init of closes, or history limit
for m in re.finditer(r"warmup|def\s+\w+closes|closes\s*=\s*|history|max_len", content, re.IGNORECASE):
    start = max(0, m.start() - 150)
    end = min(len(content), m.end() + 150)
    print(f"--- MATCH ---\n{content[start:end]}\n")
