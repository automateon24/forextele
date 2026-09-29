import json
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(r"C:\anlyzeforex\forextele")

# 1. Load Monitored Channels
monitored_acc1 = {}
monitored_acc2 = {}

ch_file1 = BASE_DIR / "telegram_channels_list.txt"
if ch_file1.exists():
    for line in ch_file1.read_text(encoding="utf-8").splitlines():
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                monitored_acc1[parts[1]] = parts[0]

ch_file2 = BASE_DIR / "telegram_channels_list2.txt"
if ch_file2.exists():
    for line in ch_file2.read_text(encoding="utf-8").splitlines():
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                monitored_acc2[parts[1]] = parts[0]

total_monitored = len(monitored_acc1) + len(monitored_acc2)
print(f"Total Monitored Dialogs/Channels: {total_monitored} (Acc1: {len(monitored_acc1)}, Acc2: {len(monitored_acc2)})")

# 2. Analyze signals_audit.csv in the last 48 hours
audit_file = BASE_DIR / "signals_audit.csv"
audit_48h = []
channel_signal_counts = defaultdict(lambda: {"total": 0, "executed": 0, "rejected": 0, "failed": 0, "reasons": defaultdict(int)})

from_48h = datetime(2026, 9, 21, 17, 0, 0)

if audit_file.exists():
    with open(audit_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 7:
                continue
            ts_str = row[0]
            try:
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
                
            if dt >= from_48h:
                channel = row[2]
                status = row[5] if len(row) > 5 else "UNKNOWN"
                reason = row[6] if len(row) > 6 else ""
                
                # Check status field format
                if len(row) >= 11: # format with Action, Symbol, Price, SL, TP, Status, Reason
                    status = row[10]
                    reason = row[11] if len(row) > 11 else ""
                elif len(row) == 8: # format with Status, Reason, Trade_Number
                    status = row[5]
                    reason = row[6]
                    
                channel_signal_counts[channel]["total"] += 1
                if "SUCCESS" in status.upper():
                    channel_signal_counts[channel]["executed"] += 1
                elif "REJECT" in status.upper():
                    channel_signal_counts[channel]["rejected"] += 1
                else:
                    channel_signal_counts[channel]["failed"] += 1
                    
                short_reason = reason[:40] if reason else "No reason"
                channel_signal_counts[channel]["reasons"][short_reason] += 1
                audit_48h.append(row)

print(f"\nSignals Logged in signals_audit.csv in last 48h: {len(audit_48h)}")
print(f"Channels that sent signals in last 48h: {len(channel_signal_counts)}")

print(f"\n{'Channel':<35} | {'Total':>5} | {'Executed':>8} | {'Rejected':>8} | {'Failed':>6} | Top Reason")
print("-" * 90)
for ch, counts in sorted(channel_signal_counts.items(), key=lambda x: x[1]["total"], reverse=True):
    top_r = sorted(counts["reasons"].items(), key=lambda x: x[1], reverse=True)
    top_reason_str = f"{top_r[0][0]} ({top_r[0][1]})" if top_r else ""
    print(f"{ch[:34]:<35} | {counts['total']:>5} | {counts['executed']:>8} | {counts['rejected']:>8} | {counts['failed']:>6} | {top_reason_str[:25]}")

# 3. Check channels that sent ZERO signals
channels_with_signals = set(channel_signal_counts.keys())
# Clean names for fuzzy match
channels_clean = {c.lower().strip() for c in channels_with_signals}

all_monitored_names = list(monitored_acc1.keys()) + list(monitored_acc2.keys())
silent_channels = []

for ch in all_monitored_names:
    ch_clean = ch.lower().strip()
    # Check if this channel sent signals
    found = any(c in ch_clean or ch_clean in c for c in channels_clean)
    if not found:
        silent_channels.append(ch)

print(f"\nChannels with ZERO signals logged in last 48h: {len(silent_channels)} out of {total_monitored}")
print("Sample silent channels (first 25):")
for sc in silent_channels[:25]:
    print(f"  - {sc}")
