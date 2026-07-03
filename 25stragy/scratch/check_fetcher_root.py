import os

root_dir = r"C:\cursor\options\niftyopt"
path = os.path.join(root_dir, "global_data_fetcher.py")
print(f"Exists in root: {os.path.exists(path)}")
