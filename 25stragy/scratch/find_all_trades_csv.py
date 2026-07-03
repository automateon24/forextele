import os
import glob
import pandas as pd

base_dir = r"C:\cursor\options\niftyopt"

print("=== Searching for all CSV trade files ===")
all_csvs = glob.glob(os.path.join(base_dir, "**", "*trades*.csv"), recursive=True)
for c in sorted(all_csvs):
    print(f"  {c} (Size: {os.path.getsize(c)} bytes)")
