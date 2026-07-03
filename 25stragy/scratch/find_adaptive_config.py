import os
import glob

base_dir = r"C:\cursor\options\niftyopt"
files = glob.glob(os.path.join(base_dir, "**", "*.py"), recursive=True) + glob.glob(os.path.join(base_dir, "*.py"))

print("=== Search for adaptive_config.json ===")
for f in files:
    if "venv" in f or "scratch" in f:
        continue
    try:
        with open(f, "r", encoding="utf-8", errors="ignore") as file:
            content = file.read()
        if "adaptive_config.json" in content:
            print(f"Found in: {f}")
            # Find lines containing it
            lines = content.splitlines()
            for idx, line in enumerate(lines):
                if "adaptive_config.json" in line:
                    print(f"  Line {idx+1}: {line.strip()}")
    except Exception as e:
        pass
