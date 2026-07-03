import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\cursor\options\niftyopt"
v3_path = os.path.join(base_dir, "united_Indian_market1.0", "engine_v3.py")

with open(v3_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== Search for Trade Entry methods in V3 ===")
for idx, line in enumerate(lines):
    if "def " in line and any(x in line.lower() for x in ["can_enter", "check_signal", "should_enter", "evaluate"]):
        print(f"{idx+1}: {line.strip()}")
        # print next 20 lines
        for j in range(idx+1, min(len(lines), idx+20)):
            print(f"  {j+1}: {lines[j].strip()}")
