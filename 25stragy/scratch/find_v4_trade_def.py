fn = r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v4.py"
with open(fn, "r", encoding="utf-8") as f:
    lines = f.readlines()
found = False
for i, line in enumerate(lines, 1):
    if "class Trade" in line:
        found = True
        print(f"Line {i}: {line.strip()}")
        for idx in range(i, min(i+40, len(lines))):
            print(f"Line {idx+1}: {lines[idx].rstrip()}")
        break
