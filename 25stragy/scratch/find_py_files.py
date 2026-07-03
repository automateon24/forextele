import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

dirs = [r"C:\25stragy", r"C:\cursor\options\niftyopt"]
active_files = []

for base_dir in dirs:
    if not os.path.exists(base_dir):
        continue
    for root, subdirs, files in os.walk(base_dir):
        # Exclude folders we don't care about
        if any(x in root.lower() for x in ["venv", "backups", "scratch", "node_modules", ".git", "__pycache__"]):
            continue
        for f in files:
            if f.endswith(".py"):
                full = os.path.join(root, f)
                active_files.append(full)
                print(f"File: {full} (Size: {os.path.getsize(full)} bytes)")

with open(r"C:\25stragy\scratch\python_files.txt", "w", encoding="utf-8") as f_out:
    for fp in active_files:
        f_out.write(fp + "\n")
