fn = r"C:\cursor\options\niftyopt\dashboard_server.py"
with open(fn, "r", encoding="utf-8") as f:
    lines = f.readlines()
print(f"Total lines: {len(lines)}")
for i, line in enumerate(lines[-50:], len(lines) - 49):
    print(f"Line {i}: {line.strip()}")
