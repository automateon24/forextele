import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

src_tests = r"C:\cursor\options\niftyopt\tests"
dest_tests = r"C:\25stragy\tests"

try:
    if os.path.exists(dest_tests):
        shutil.rmtree(dest_tests)
    shutil.copytree(src_tests, dest_tests)
    print("Successfully copied tests directory to", dest_tests)
except Exception as e:
    print("Error copying tests directory:", e)
