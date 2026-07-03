fn = r"C:\cursor\options\niftyopt\united_Indian_market1.0\global_data_fetcher.py"
with open(fn, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "class OptionContract" in line or "class MarketData" in line:
            print(f"Line {i}: {line.strip()}")
