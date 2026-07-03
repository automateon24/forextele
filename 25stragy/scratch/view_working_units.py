import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\25stragy\TEST_FRAMEWORK\working_unit_tests.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.read().splitlines()

for i in range(60, min(100, len(lines))):
    print(f"  Line {i+1}: {lines[i]}")
