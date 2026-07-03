fn = r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v15.py"
print(f"References to client in {fn}:")
with open(fn, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "client" in line or "DataFetcher" in line or "Fetcher" in line:
            print(f"Line {i}: {line.strip()}")
