import sys, os
sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd

# Check if option parquet data covers May 2026
data_dir = r'c:\cursor\options\niftyopt\data\options_1min'
if not os.path.exists(data_dir):
    data_dir = r'c:\cursor\options\niftyopt\data'

# Find all parquet files
import glob
parquets = glob.glob(r'c:\cursor\options\niftyopt\**\*.parquet', recursive=True)
parquets = [p for p in parquets if 'venv' not in p]
print(f"Found {len(parquets)} parquet files")
if parquets:
    for p in sorted(parquets)[:5]:
        print(f"  {p}")
    print("  ...")

# Also check the actual data loader path
from BACKTEST_V3_TUNED import load_option_data
opt = load_option_data()
dates = sorted(opt['date'].unique())
print(f"\nOption data: {len(dates)} days from {str(dates[0])[:10]} to {str(dates[-1])[:10]}")

target = ['2026-04-30','2026-05-04','2026-05-05','2026-05-06',
          '2026-05-07','2026-05-08','2026-05-11','2026-05-12','2026-05-13','2026-05-14']
print("\nManual trade dates coverage:")
for d in target:
    found = any(str(x)[:10] == d for x in dates)
    print(f"  {d}: {'YES - have data' if found else 'NO - missing'}")
