import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

src_dir = r"C:\cursor\options\niftyopt\archive\old_scripts"
dest_dir = r"C:\25stragy"

files = ["real_dhan_api_only_system.py", "ultra_optimized_40_percent.py"]

for f in files:
    src_path = os.path.join(src_dir, f)
    dest_path = os.path.join(dest_dir, f)
    if os.path.exists(src_path):
        shutil.copy(src_path, dest_path)
        print(f"Copied {f} to {dest_dir}")
    else:
        print(f"Could not find {src_path}")
