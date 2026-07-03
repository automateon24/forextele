import os

base_dir = r"C:\cursor\options\niftyopt"
v3_path = os.path.join(base_dir, "united_Indian_market1.0", "engine_v3.py")

with open(v3_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== Active Modules in V3 ===")
found_init = False
for idx, line in enumerate(lines):
    if "self.modules" in line:
        found_init = True
        # print next 30 lines
        for j in range(idx, min(len(lines), idx+35)):
            print(f"{j+1}: {lines[j].strip()}")
        break
