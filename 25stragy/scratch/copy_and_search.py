import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

src_dir = r"C:\cursor\options\niftyopt"
dest_dir = r"C:\25stragy"

# Copy V3 and V4 traders
for f in ["MODULAR_TRADER_V3.py", "MODULAR_TRADER_V4.py"]:
    shutil.copy(os.path.join(src_dir, f), os.path.join(dest_dir, f))
    print(f"Copied {f} to {dest_dir}")

# Look for files with 'v15' or 'adaptive' in their names in united_Indian_market1.0
u_dir = os.path.join(src_dir, "united_Indian_market1.0")
if os.path.exists(u_dir):
    print("Files in united_Indian_market1.0:")
    for f in os.listdir(u_dir):
        if any(x in f.lower() for x in ["v15", "adaptive", "v3", "v4"]):
            print(f"  {f}")
