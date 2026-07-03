import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\25stragy\BACKTEST_V15_HYBRID_AGGRESSIVE.py"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.read().splitlines()

for idx, line in enumerate(lines):
    if "def main" in line or "sys.argv" in line or "argparse" in line or "if __name__" in line or "run_backtest" in line:
        print(f"Line {idx+1}: {line.strip()}")
