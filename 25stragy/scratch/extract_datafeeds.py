import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\cursor\options\niftyopt"
engine_v3_path = os.path.join(base_dir, "united_Indian_market1.0", "engine_v3.py")
engine_v4_path = os.path.join(base_dir, "united_Indian_market1.0", "engine_v4.py")

def extract_datafeed_code(path, label):
    print(f"\n==================== {label} ====================")
    if not os.path.exists(path):
        print("File not found")
        return
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    start_line = -1
    for i, line in enumerate(lines):
        if "class DataFeed" in line:
            start_line = i
            break
            
    if start_line != -1:
        print(f"Found class DataFeed starting at line {start_line+1}")
        # Print up to 180 lines
        end_line = min(len(lines), start_line + 180)
        for idx in range(start_line, end_line):
            print(f"{idx+1}: {lines[idx].strip()}")
    else:
        print("class DataFeed not found")

extract_datafeed_code(engine_v3_path, "Engine V3")
extract_datafeed_code(engine_v4_path, "Engine V4")
