import shutil
import os

src_v3 = r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v3.py"
dst_v3 = r"C:\cursor\options\niftyopt\MODULAR_TRADER_V3.py"

src_v4 = r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v4.py"
dst_v4 = r"C:\cursor\options\niftyopt\MODULAR_TRADER_V4.py"

src_v15 = r"C:\cursor\options\niftyopt\LIVE_PORTFOLIO_TRADER.py"
dst_v15 = r"C:\cursor\options\niftyopt\united_Indian_market1.0\engine_v15.py"

print("=== Copying Engine Files ===")
try:
    shutil.copy2(src_v3, dst_v3)
    print(f"Copied V3: {src_v3} -> {dst_v3}")
except Exception as e:
    print(f"Error copying V3: {e}")

try:
    shutil.copy2(src_v4, dst_v4)
    print(f"Copied V4: {src_v4} -> {dst_v4}")
except Exception as e:
    print(f"Error copying V4: {e}")

try:
    shutil.copy2(src_v15, dst_v15)
    print(f"Copied V15: {src_v15} -> {dst_v15}")
except Exception as e:
    print(f"Error copying V15: {e}")
