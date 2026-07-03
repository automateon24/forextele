import os
import glob
import pandas as pd
from datetime import datetime, timedelta

sys_stdout = open(1, 'w', encoding='utf-8', closefd=False)

base_dir = r"C:\cursor\options\niftyopt"
daily_data_dir = os.path.join(base_dir, "daily_data")
data_dir = os.path.join(base_dir, "data")

print("=== Scanning daily_data directory ===")
all_daily_files = glob.glob(os.path.join(daily_data_dir, "*"))
for f in sorted(all_daily_files)[-30:]:
    print(f"  {os.path.basename(f)} (Size: {os.path.getsize(f)} bytes)")

print("\n=== Scanning data directory ===")
all_data_files = glob.glob(os.path.join(data_dir, "*"))
for f in sorted(all_data_files):
    print(f"  {os.path.basename(f)} (Size: {os.path.getsize(f)} bytes)")
