import json

with open(r"C:\anlyzeforex\forextele\scratch\full_telegram_scrape_today.json", encoding="utf-8") as f:
    data = json.load(f)

mt = data["channels"]["Market Trader Crypto Forex"]
print("ALL DETECTED SIGNALS:")
for s in mt.get("signals", []):
    print(f"Time: {s['time']} | ID: {s['id']}")
    print(f"Text: {s['text']}")
    print(f"Signal: {s['signal']}")
    print("-" * 50)

# Let's also check if there are other channels named Market Trader or similar
for ch_name, d in data["channels"].items():
    if "market" in ch_name.lower() or "trader" in ch_name.lower():
        if d.get("total_messages_today", 0) > 0:
            print(f"Found related channel: {ch_name} (ID: {d.get('id')}, msgs: {d.get('total_messages_today')}, signals: {d.get('signals_detected')})")
