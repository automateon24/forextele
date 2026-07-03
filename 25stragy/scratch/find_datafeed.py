with open(r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v3.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "DataFeed" in line:
            print(f"Line {i}: {line.strip()}")
