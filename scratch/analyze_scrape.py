import json
from pathlib import Path
from datetime import datetime, timezone

# Let's inspect all channels that have signals or messages today from full_telegram_scrape_today.json
scrape_file = Path(r"C:\anlyzeforex\forextele\scratch\full_telegram_scrape_today.json")
with open(scrape_file, encoding='utf-8') as f:
    data = json.load(f)

channels = data.get("channels", {})
print(f"Total channels in scrape: {len(channels)}")

# Let's find all channels with messages today
active_channels = {k: v for k, v in channels.items() if v.get("total_messages_today", 0) > 0}
print(f"Active channels with messages today: {len(active_channels)}")

# Let's see which channels have signals
sig_channels = {k: v for k, v in active_channels.items() if v.get("signals_detected", 0) > 0}
print(f"Channels with signals detected by basic parser: {len(sig_channels)}")

# Print all channels with signals detected
for ch, d in sorted(sig_channels.items(), key=lambda x: x[1]["signals_detected"], reverse=True):
    print(f"  {ch} ({d.get('account')}): {d.get('signals_detected')} signals, {d.get('total_messages_today')} msgs")
