import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\cursor\options\niftyopt"
v3_log = os.path.join(base_dir, "daily_data", "v3_20260625.log")
v4_log = os.path.join(base_dir, "daily_data", "modular_20260625.log")

print("=== V3 Live Session Log Inspection ===")
if os.path.exists(v3_log):
    with open(v3_log, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    print(f"Total log lines: {len(lines)}")
    # Print lines indicating live connection, orders, or websocket ticks
    matches = 0
    for line in lines:
        line_lower = line.lower()
        if "connect" in line_lower or "websocket" in line_lower or "order" in line_lower or "placed" in line_lower or "tick" in line_lower:
            print(line.strip())
            matches += 1
            if matches >= 15:
                break
else:
    print("V3 log not found")

print("\n=== V4 Live Session Log Inspection ===")
if os.path.exists(v4_log):
    with open(v4_log, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    print(f"Total log lines: {len(lines)}")
    matches = 0
    for line in lines:
        line_lower = line.lower()
        if "connect" in line_lower or "websocket" in line_lower or "order" in line_lower or "placed" in line_lower or "tick" in line_lower:
            print(line.strip())
            matches += 1
            if matches >= 15:
                break
else:
    print("V4 log not found")
