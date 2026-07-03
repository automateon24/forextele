import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Copy V15 engine
shutil.copy(r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v15.py", r"C:\25stragy\engine_v15.py")
print("Copied engine_v15.py to C:\\25stragy")

# Search codebase for 'adaptive'
search_paths = [r"C:\25stragy", r"C:\cursor\options\niftyopt"]
found_refs = []

print("=== References to 'adaptive' in files ===")
for sp in search_paths:
    if not os.path.exists(sp):
        continue
    for root, dirs, files in os.walk(sp):
        if any(x in root.lower() for x in ["venv", "backups", "scratch", "node_modules", ".git", "__pycache__"]):
            continue
        for f in files:
            if f.endswith((".py", ".bat", ".json", ".sh")):
                fp = os.path.join(root, f)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as file_in:
                        content = file_in.read()
                    if "adaptive" in content.lower():
                        print(f"  {fp}")
                except Exception as e:
                    pass
