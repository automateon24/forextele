import os

root_dir = r"C:\cursor\options\niftyopt"

def search_in_file(path, query):
    if not os.path.exists(path):
        return f"{os.path.basename(path)} does not exist."
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.splitlines()
    matches = []
    for idx, line in enumerate(lines):
        if query.lower() in line.lower():
            matches.append(f"  Line {idx+1}: {line.strip()}")
    return matches

print("=== Search for 'adaptive_config' in root V15 ===")
for m in search_in_file(os.path.join(root_dir, "LIVE_PORTFOLIO_TRADER.py"), "adaptive_config")[:10]:
    print(m)

print("=== Search for 'adaptive_config' in root V3 ===")
for m in search_in_file(os.path.join(root_dir, "MODULAR_TRADER_V3.py"), "adaptive_config")[:10]:
    print(m)

print("=== Search for 'vwap' in root V15 ===")
for m in search_in_file(os.path.join(root_dir, "LIVE_PORTFOLIO_TRADER.py"), "vwap")[:10]:
    print(m)
