import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

search_dirs = [r"C:\cursor\options\niftyopt", r"C:\25stragy"]
targets = ["real_dhan_api_only_system.py", "ultra_optimized_40_percent.py"]

print("=== Searching for files ===")
for d in search_dirs:
    if not os.path.exists(d):
        continue
    for root, dirs, files in os.walk(d):
        for f in files:
            if f in targets:
                print(f"Found: {os.path.join(root, f)}")
