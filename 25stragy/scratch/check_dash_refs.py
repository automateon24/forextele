import os

base_dir = r"C:\cursor\options\niftyopt"
dash_path = os.path.join(base_dir, "dashboard_server.py")

with open(dash_path, "r", encoding="utf-8") as f:
    content = f.read()

print("=== References in dashboard_server.py ===")
for idx, line in enumerate(content.splitlines()):
    if any(x in line for x in ["united_Indian_market1", "MODULAR_TRADER", "LIVE_PORTFOLIO", "engine_v"]):
        print(f"  Line {idx+1}: {line.strip()}")
