import sys
sys.path.append(r'C:\cursor\options\niftyopt\united_Indian_market1.0')

print("Testing imports...")

try:
    import global_data_fetcher
    print("global_data_fetcher imported successfully")
except Exception as e:
    print(f"global_data_fetcher import failed: {e}")

try:
    import engine_v3
    print("engine_v3 imported successfully")
except Exception as e:
    print(f"engine_v3 import failed: {e}")

try:
    import engine_v4
    print("engine_v4 imported successfully")
except Exception as e:
    print(f"engine_v4 import failed: {e}")

try:
    import engine_v15
    print("engine_v15 imported successfully")
except Exception as e:
    print(f"engine_v15 import failed: {e}")
