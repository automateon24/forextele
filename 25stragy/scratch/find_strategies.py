import os
import glob
import sys

sys.stdout.reconfigure(encoding='utf-8')

search_dirs = [r"C:\cursor\options\niftyopt", r"C:\25stragy"]
patterns = ["*v3*", "*v4*", "*v15*", "*adaptive*", "BACKTEST_*"]

print("=== Found Strategy/Backtest Files ===")
found_files = []
for d in search_dirs:
    if not os.path.exists(d):
        continue
    for root, dirs, files in os.walk(d):
        # Skip virtual env directories to keep results clean
        if "venv" in root or ".git" in root or "node_modules" in root:
            continue
        for f in files:
            name_lower = f.lower()
            match = False
            for p in patterns:
                p_clean = p.replace("*", "").lower()
                if p_clean in name_lower:
                    match = True
                    break
            if match or f.startswith("BACKTEST_"):
                full_path = os.path.join(root, f)
                found_files.append(full_path)
                print(f"  {full_path} (Size: {os.path.getsize(full_path)} bytes)")

# Write paths to a temporary file
with open("C:\\25stragy\\scratch\\strategy_files.txt", "w", encoding="utf-8") as f_out:
    for fp in found_files:
        f_out.write(fp + "\n")
