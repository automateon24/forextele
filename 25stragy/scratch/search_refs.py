import os
import re

search_files = [
    r"C:\cursor\options\niftyopt\dashboard_server.py",
    r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v3.py",
    r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v4.py",
    r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v15.py",
    r"C:\cursor\options\niftyopt\united_Indian_market1.0\global_data_fetcher.py"
]

patterns = [
    r"united_Indian_market",
    r"MODULAR_TRADER_V3",
    r"MODULAR_TRADER_V4",
    r"LIVE_PORTFOLIO_TRADER"
]

results = []
for path in search_files:
    if not os.path.exists(path):
        print(f"File not found: {path}")
        continue
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for pat in patterns:
            if re.search(pat, content, re.IGNORECASE):
                lines = content.splitlines()
                for i, l in enumerate(lines, 1):
                    if pat.lower() in l.lower():
                        results.append((path, i, pat, l.strip()))
    except Exception as e:
        print(f"Error reading {path}: {e}")

print(f"Found {len(results)} references:")
for r in results:
    print(f"{os.path.basename(r[0])}:{r[1]} [{r[2]}] -> {r[3]}")
