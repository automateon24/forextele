import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\25stragy\engine_v15.py"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.read().splitlines()

for idx, line in enumerate(lines):
    if "log" in line.lower() or "csv" in line.lower() or "_file" in line.lower():
        print(f"Line {idx+1}: {line.strip()}")
