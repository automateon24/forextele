import os

log_path = r"C:\cursor\options\niftyopt\data\live_portfolio_trader.log"
if not os.path.exists(log_path):
    print("Log file does not exist!")
    sys.exit(0)

with open(log_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines in log: {len(lines)}")
print("=== Last 100 lines ===")
for line in lines[-100:]:
    print(line.strip())
