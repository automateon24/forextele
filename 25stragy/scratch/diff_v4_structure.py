import difflib
import os

root_dir = r"C:\cursor\options\niftyopt"
f1_path = os.path.join(root_dir, "MODULAR_TRADER_V4.py")
f2_path = os.path.join(root_dir, "united_Indian_market1.0", "engine_v4.py")

with open(f1_path, "r", encoding="utf-8") as f:
    f1_lines = f.readlines()
with open(f2_path, "r", encoding="utf-8") as f:
    f2_lines = f.readlines()

print(f"File 1 (Root V4): {len(f1_lines)} lines")
print(f"File 2 (Sub V4): {len(f2_lines)} lines")

# Let's check the top level definitions (class, def) to see if they differ structurally
def get_structure(lines):
    struct = []
    for idx, line in enumerate(lines):
        if line.strip().startswith("class ") or (line.strip().startswith("def ") and not line.startswith(" ")):
            struct.append((idx+1, line.strip()))
    return struct

struct1 = get_structure(f1_lines)
struct2 = get_structure(f2_lines)

print("\n=== Root V4 Classes/Global functions ===")
for idx, s in struct1:
    print(f"  {idx}: {s}")

print("\n=== Sub V4 Classes/Global functions ===")
for idx, s in struct2:
    print(f"  {idx}: {s}")
