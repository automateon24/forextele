import os
import time
from datetime import datetime, timedelta

base_dir = r"C:\cursor\options\niftyopt"
dirs_to_check = [
    os.path.join(base_dir, "daily_data"),
    os.path.join(base_dir, "trades"),
    os.path.join(base_dir, "logs"),
    base_dir
]

one_week_ago = datetime.now() - timedelta(days=8) # 8 days to catch everything
print(f"Checking for files modified since {one_week_ago.strftime('%Y-%m-%d')}")

recent_files = []
for d in dirs_to_check:
    if not os.path.exists(d):
        continue
    for item in os.listdir(d):
        path = os.path.join(d, item)
        if os.path.isfile(path):
            mtime = os.path.getmtime(path)
            mtime_dt = datetime.fromtimestamp(mtime)
            if mtime_dt > one_week_ago:
                recent_files.append((path, mtime_dt, os.path.getsize(path)))

recent_files.sort(key=lambda x: x[1], reverse=True)
print(f"Found {len(recent_files)} recently modified files:")
for path, mtime, size in recent_files[:50]:
    rel_path = os.path.relpath(path, base_dir)
    print(f" - {rel_path} (Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}, Size: {size} bytes)")
