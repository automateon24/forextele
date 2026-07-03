import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\cursor\options\niftyopt"
log_path = os.path.join(base_dir, "adaptive_data", "adaptive_engine.log")
config_path = os.path.join(base_dir, "adaptive_data", "adaptive_config.json")

print("=== adaptive_config.json Content ===")
if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            print(json.dumps(json.load(f), indent=2))
    except Exception as e:
        print(f"Error reading config: {e}")
else:
    print("Config file not found")

print("\n=== Recent adaptive_engine.log lines ===")
if os.path.exists(log_path):
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        # Find lines from past 1 week (containing 2026-06-18 to 2026-06-25)
        recent_lines = []
        for line in lines:
            if any(f"2026-06-{day}" in line for day in range(18, 26)):
                if "regime" in line.lower() or "tune" in line.lower() or "switch" in line.lower() or "detect" in line.lower() or "pcr" in line.lower():
                    recent_lines.append(line.strip())
                    
        print(f"Total recent log lines matching: {len(recent_lines)}")
        for line in recent_lines[-30:]:
            print(line)
    except Exception as e:
        print(f"Error reading log: {e}")
else:
    print("Log file not found")
