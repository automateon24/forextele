import os
import glob

base_dir = r"C:\cursor\options\niftyopt"
daily_data_dir = os.path.join(base_dir, "daily_data")

v4_files = glob.glob(os.path.join(daily_data_dir, "*modular*"))
print("=== Modular (V4) files found ===")
for f in sorted(v4_files):
    print(f"  {os.path.basename(f)} (Size: {os.path.getsize(f)} bytes)")
