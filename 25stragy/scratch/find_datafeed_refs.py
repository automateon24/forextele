for fn in [r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v3.py", r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v4.py"]:
    print(f"\nReferences in {fn}:")
    with open(fn, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if "data_feed" in line or "datafeed" in line:
                print(f"Line {i}: {line.strip()}")
