import json
from pathlib import Path

with open(r"C:\anlyzeforex\forextele\scratch\full_day_audit_report.json", encoding="utf-8") as f:
    d = json.load(f)

print("SUMMARY:", d.get("summary"))
print("\nCHANNEL BREAKDOWN:")
for ch, stats in d.get("channel_breakdown", {}).items():
    print(f"  {ch:<30} | {stats['trades']:>2} trades | {stats['wins']:>2}W/{stats['losses']:>2}L ({stats['win_rate']:>5}) | Net PnL: ${stats['net_pnl']:>7.2f}")
