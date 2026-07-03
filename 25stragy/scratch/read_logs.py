import os

base_dir = r"C:\cursor\options\niftyopt"
log_files = [
    os.path.join(base_dir, "logs", "scheduler.log"),
    os.path.join(base_dir, "logs", "daily_status.log"),
    os.path.join(base_dir, "logs", "auto_renew.log")
]

print("=== LOG ANALYSIS ===")
for lf in log_files:
    if not os.path.exists(lf):
        print(f"Log not found: {lf}")
        continue
    print(f"\n--- Reading {os.path.basename(lf)} (Last 50 lines) ---")
    with open(lf, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        for line in lines[-50:]:
            print(line.strip())
