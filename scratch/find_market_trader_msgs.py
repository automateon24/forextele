import json
from pathlib import Path

# Search in full_telegram_scrape_today.json
scrape_file = Path(r"C:\anlyzeforex\forextele\scratch\full_telegram_scrape_today.json")
with open(scrape_file, encoding='utf-8') as f:
    data = json.load(f)

print("=== SEARCHING FOR MARKET TRADER IN FULL SCRAPE ===")
for ch_name, ch_data in data.get('channels', {}).items():
    if any(k in ch_name.lower() for k in ['market', 'trader', 'crypto', 'forex']):
        print(f"\nChannel: {ch_name} (Account: {ch_data.get('account')}, ID: {ch_data.get('id')})")
        print(f"Total msgs: {ch_data.get('total_messages_today')}, Signals: {ch_data.get('signals_detected')}")
        for m in ch_data.get('signals', []):
            print(f"  Signal: {m.get('time')} - {m.get('signal')}")
            print(f"    Raw: {m.get('text')[:150]!r}")
