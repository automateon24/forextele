import os

base_dir = r"C:\cursor\options\niftyopt"
engine_v3_path = os.path.join(base_dir, "united_Indian_market1.0", "engine_v3.py")
engine_v4_path = os.path.join(base_dir, "united_Indian_market1.0", "engine_v4.py")

def check_indicator_attributes(path, label):
    print(f"\n=== Indicator Attributes in {label} ===")
    if not os.path.exists(path):
        print("File not found")
        return
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    matches = 0
    for idx, line in enumerate(lines):
        if any(kw in line for kw in ["rsi14", "ema20", "ema5", "data.closes"]):
            print(f"{idx+1}: {line.strip()}")
            matches += 1
            if matches >= 40:
                print("... truncated ...")
                break

check_indicator_attributes(engine_v3_path, "Engine V3")
check_indicator_attributes(engine_v4_path, "Engine V4")
