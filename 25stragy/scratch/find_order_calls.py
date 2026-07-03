import os

path = r"C:\cursor\options\niftyopt\LIVE_PORTFOLIO_TRADER.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print("=== Dhan/Order References in LIVE_PORTFOLIO_TRADER.py ===")
for idx, line in enumerate(content.splitlines()):
    if any(x in line.lower() for x in ["order", "dhan", "buy", "sell", "client"]):
        if not line.strip().startswith("#"):
            print(f"  Line {idx+1}: {line.strip()}")
