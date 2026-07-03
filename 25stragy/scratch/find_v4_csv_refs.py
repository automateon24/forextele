fn = r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v4.py"
print(f"References in {fn}:")
with open(fn, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if ".csv" in line.lower() or "csv" in line.lower() or "trade_log" in line.lower():
            print(f"Line {i}: {line.strip()}")
