import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

src_file = r"C:\cursor\options\niftyopt\regime_detector.py"
dest_file = r"C:\25stragy\regime_detector.py"

if os.path.exists(src_file):
    shutil.copy(src_file, dest_file)
    print("Copied regime_detector.py to C:\\25stragy")
else:
    print("regime_detector.py not found in C:\\cursor\\options\\niftyopt")
