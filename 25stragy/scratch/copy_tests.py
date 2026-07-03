import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

src_dir = r"C:\cursor\options\niftyopt\TEST_FRAMEWORK"
dest_dir = r"C:\25stragy\TEST_FRAMEWORK"

try:
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    shutil.copytree(src_dir, dest_dir)
    print("Successfully copied TEST_FRAMEWORK to", dest_dir)
except Exception as e:
    print("Error copying TEST_FRAMEWORK:", e)
