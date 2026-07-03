import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

test_dir = r"C:\25stragy\TEST_FRAMEWORK"
py_files = glob.glob(os.path.join(test_dir, "*.py"))

print("=== Hardcoded Paths in Test Framework ===")
for pf in py_files:
    with open(pf, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    for idx, line in enumerate(lines):
        if "C:\\" in line or "C:/" in line or ".py" in line or "json" in line:
            # Print if it looks like a path assignment
            if "=" in line and any(x in line for x in ["path", "file", "dir"]):
                print(f"  {os.path.basename(pf)}:Line {idx+1}: {line.strip()}")
