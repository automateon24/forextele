import os
import shutil

src_dir = r"C:\cursor\options\niftyopt"
dst_dir = r"C:\cursor\options\niftyopt\united_Indian_market1.0\learnings_history"

if not os.path.exists(dst_dir):
    os.makedirs(dst_dir)

keywords = ["guide", "dna", "changelog", "readme", "analysis", "enhancement", "revival", "summary", "parameter", "pre_flight"]

files_to_copy = []
for file in os.listdir(src_dir):
    path = os.path.join(src_dir, file)
    if os.path.isfile(path):
        name_lower = file.lower()
        if any(kw in name_lower for kw in keywords) and file.endswith(('.md', '.txt', '.json')):
            files_to_copy.append(file)

print("Files to copy:")
for file in files_to_copy:
    src_path = os.path.join(src_dir, file)
    dst_path = os.path.join(dst_dir, file)
    shutil.copy2(src_path, dst_path)
    print(f"Copied {file} -> learnings_history/{file}")
