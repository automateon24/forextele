import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\25stragy\scratch\python_files.txt"
with open(path, "r", encoding="utf-8") as f:
    lines = f.read().splitlines()

print("=== User Strategy Files ===")
for line in lines:
    line_lower = line.lower()
    # Filter out virtual environments, dependencies, site-packages, etc.
    if any(x in line_lower for x in ["site-packages", "lib", "trading_env", "node_modules", "package", "env", "dist-packages"]):
        continue
    print(f"  {line}")
