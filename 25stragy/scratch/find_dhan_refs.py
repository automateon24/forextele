import os

files = [
    r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v3.py",
    r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v4.py"
]

for fn in files:
    if not os.path.exists(fn):
        print(f"File not found: {fn}")
        continue
    print(f"=== References in {fn} ===")
    with open(fn, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if "dhanhq" in line.lower() or "dhan(" in line.lower() or "access_token" in line.lower() or "get_global_data_fetcher" in line:
                print(f"Line {i}: {line.strip()}")
