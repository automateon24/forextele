import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

raw_dir = r"C:\cursor\options\niftyopt\data\raw"
if os.path.exists(raw_dir):
    files = glob.glob(os.path.join(raw_dir, "*"))
    print(f"Total files in raw data: {len(files)}")
    # Print the first 20 files
    for f in files[:20]:
        print(f"  {os.path.basename(f)}")
else:
    print("raw data directory not found")
