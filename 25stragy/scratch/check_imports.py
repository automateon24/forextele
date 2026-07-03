import os

root_dir = r"C:\cursor\options\niftyopt"
files = ["LIVE_PORTFOLIO_TRADER.py", "MODULAR_TRADER_V3.py", "MODULAR_TRADER_V4.py"]

for f_name in files:
    path = os.path.join(root_dir, f_name)
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"=== Imports/References in {f_name} ===")
    for line in content.splitlines():
        if "united_Indian_market1" in line or "engine_v" in line or "global_data_fetcher" in line:
            print(f"  {line.strip()}")
