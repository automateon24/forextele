import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\cursor\options\niftyopt"
v3_log = os.path.join(base_dir, "daily_data", "v3_20260625.log")
v4_log = os.path.join(base_dir, "daily_data", "modular_20260625.log")

print("=== V3 Log Exit Lines ===")
if os.path.exists(v3_log):
    with open(v3_log, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    for line in lines[-20:]:
        print(line.strip())
else:
    print("V3 log not found")

print("\n=== V4 Log Exit Lines ===")
if os.path.exists(v4_log):
    with open(v4_log, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    for line in lines[-20:]:
        print(line.strip())
else:
    print("V4 log not found")
