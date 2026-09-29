import json
from pathlib import Path

scrape_file = Path(r"C:\anlyzeforex\forextele\scratch\full_telegram_scrape_today.json")
with open(scrape_file, encoding='utf-8') as f:
    data = json.load(f)

print("SUMMARY:")
print(json.dumps(data.get("summary", {}), indent=2))

print("\nCHANNELS WITH SIGNALS:")
for ch, d in data.get("channels", {}).items():
    sig_count = d.get("signals_detected", 0)
    if sig_count > 0:
        print(f"  - {ch} [{d.get('account')}]: {sig_count} signals (Total msgs: {d.get('total_messages_today')})")
        # Print sample signals
        for s in d.get("signals", [])[:3]:
            sig_info = s.get("signal", {})
            print(f"      {s.get('time')}: {sig_info.get('action')} {sig_info.get('symbols')} entry={sig_info.get('entry')} sl={sig_info.get('sl')} tps={sig_info.get('tps')}")
            print(f"      text: {s.get('text')[:120].strip()!r}")
