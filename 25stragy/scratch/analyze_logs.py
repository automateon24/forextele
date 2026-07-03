import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

v3_log = r"C:\cursor\options\niftyopt\daily_data\v3_20260625.log"
v4_log = r"C:\cursor\options\niftyopt\daily_data\modular_20260625.log"
v15_log = r"C:\cursor\options\niftyopt\data\live_portfolio_trader.log"

print("========================================")
print("LOG ANALYSIS: TRIGGERS & ERRORS FOR JUNE 25")
print("========================================\n")

def analyze_v3_log():
    if not os.path.exists(v3_log):
        print("V3 log not found.")
        return
    print("--- V3 LOG SIGNALS & TRIGGERS ---")
    entry_signals = 0
    exits = 0
    errors = 0
    with open(v3_log, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "[SIGNAL]" in line or "ENTER" in line or "ENTRY" in line:
                print(f"  {line.strip()[:120]}")
                entry_signals += 1
            elif "EXIT" in line or "Closed position" in line:
                print(f"  {line.strip()[:120]}")
                exits += 1
            elif "ERROR" in line or "Exception" in line or "failed" in line.lower() or "805" in line:
                if any(x in line for x in ["ticker", "chain", "Option chain", "rate limit", "805", "Too many"]):
                    print(f"  [ERROR] {line.strip()[:120]}")
                    errors += 1
    print(f"Summary V3: Entries/Signals={entry_signals}, Exits={exits}, Errors={errors}\n")

def analyze_v4_log():
    if not os.path.exists(v4_log):
        print("V4 log not found.")
        return
    print("--- V4/MODULAR LOG SIGNALS & TRIGGERS ---")
    entry_signals = 0
    exits = 0
    errors = 0
    with open(v4_log, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "ENTER" in line or "Signal:" in line:
                print(f"  {line.strip()[:120]}")
                entry_signals += 1
            elif "EXIT" in line or "Exit signal:" in line:
                print(f"  {line.strip()[:120]}")
                exits += 1
            elif "ERROR" in line or "Exception" in line or "failed" in line.lower() or "805" in line:
                if any(x in line for x in ["ticker", "chain", "Option chain", "rate limit", "805", "Too many"]):
                    print(f"  [ERROR] {line.strip()[:120]}")
                    errors += 1
    print(f"Summary V4: Entries/Signals={entry_signals}, Exits={exits}, Errors={errors}\n")

def analyze_v15_log():
    if not os.path.exists(v15_log):
        print("V15 log not found.")
        return
    print("--- V15 LOG EXECUTIONS & ERRORS ---")
    errors = 0
    entries = 0
    skips = 0
    with open(v15_log, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "[ENTRY]" in line:
                print(f"  {line.strip()[:120]}")
                entries += 1
            elif "Skipped" in line:
                if "Drawdown Circuit Breaker" in line:
                    # Let's count these but not print all to avoid flooding
                    skips += 1
                else:
                    print(f"  [SKIP] {line.strip()[:120]}")
            elif "805" in line or "Too many requests" in line:
                errors += 1
    print(f"Summary V15: Entries={entries}, Skips={skips}, API 805 Rate Limit Errors={errors}\n")

analyze_v3_log()
analyze_v4_log()
analyze_v15_log()
