import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

src_dir = r"C:\cursor\options\niftyopt"
dest_dir = r"C:\25stragy"

# Files to copy
files_to_copy = [
    "real_dhan_api_only_system.py",
    "ultra_optimized_40_percent.py"
]

# Folders to copy
folders_to_copy = [
    "logs"
]

for f in files_to_copy:
    src_f = os.path.join(src_dir, f)
    dest_f = os.path.join(dest_dir, f)
    if os.path.exists(src_f):
        shutil.copy(src_f, dest_f)
        print(f"Copied file {f} to {dest_dir}")
    else:
        print(f"File {f} not found in {src_dir}")

for d in folders_to_copy:
    src_d = os.path.join(src_dir, d)
    dest_d = os.path.join(dest_dir, d)
    if os.path.exists(src_d):
        if os.path.exists(dest_d):
            shutil.rmtree(dest_d)
        shutil.copytree(src_d, dest_d)
        print(f"Copied folder {d} to {dest_dir}")
    else:
        print(f"Folder {d} not found in {src_dir}")
