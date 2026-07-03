fn = r"C:\cursor\options\niftyopt\dashboard_server.py"
with open(fn, "r", encoding="utf-8") as f:
    lines = f.readlines()

found = False
for i, line in enumerate(lines, 1):
    if "def load_modular_trades" in line:
        found = True
        print(f"Found on line {i}")
        for j in range(max(0, i-5), min(len(lines), i+60)):
            print(f"Line {j+1}: {lines[j].strip()}")
        break
if not found:
    print("load_modular_trades not found")
