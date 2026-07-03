import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\cursor\options\niftyopt\dashboard_server.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print("=== Search for EOD Report UI code ===")
for idx, line in enumerate(content.splitlines()):
    if any(x in line for x in ["eodReportBtn", "viewEodReport", "eod_report"]):
        print(f"  Line {idx+1}: {line.strip()}")
