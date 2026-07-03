import filecmp
import os

root_dir = r"C:\cursor\options\niftyopt"
sub_dir = os.path.join(root_dir, "united_Indian_market1.0")

pairs = [
    (os.path.join(root_dir, "LIVE_PORTFOLIO_TRADER.py"), os.path.join(sub_dir, "engine_v15.py")),
    (os.path.join(root_dir, "MODULAR_TRADER_V3.py"), os.path.join(sub_dir, "engine_v3.py")),
    (os.path.join(root_dir, "MODULAR_TRADER_V4.py"), os.path.join(sub_dir, "engine_v4.py")),
    (os.path.join(root_dir, "united_Indian_market1.0", "global_data_fetcher.py"), os.path.join(root_dir, "united_Indian_market1.0", "global_data_fetcher.py")) # self comparison
]

print("=== Comparing root vs sub-folder files ===")
for root_file, sub_file in pairs[:-1]:
    if not os.path.exists(root_file):
        print(f"Root file missing: {root_file}")
        continue
    if not os.path.exists(sub_file):
        print(f"Sub file missing: {sub_file}")
        continue
    
    match = filecmp.cmp(root_file, sub_file, shallow=False)
    print(f"{os.path.basename(root_file)} vs {os.path.basename(sub_file)}: {'MATCH' if match else 'DIFFERENT'}")
    if not match:
        print(f"  Root file size: {os.path.getsize(root_file)} bytes")
        print(f"  Sub file size: {os.path.getsize(sub_file)} bytes")
