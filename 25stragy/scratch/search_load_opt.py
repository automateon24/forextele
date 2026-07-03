import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\25stragy\BACKTEST_V15_HYBRID_AGGRESSIVE.py"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.read().splitlines()

found = False
for idx, line in enumerate(lines):
    if "def load_option_data_for_index" in line:
        # print 50 lines from here
        for j in range(idx, min(idx + 50, len(lines))):
            print(f"Line {j+1}: {lines[j]}")
        found = True
        break
