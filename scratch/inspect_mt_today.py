import json

with open(r"C:\anlyzeforex\forextele\scratch\full_telegram_scrape_today.json", encoding="utf-8") as f:
    data = json.load(f)

mt = data["channels"]["Market Trader Crypto Forex"]
print(f"ID: {mt['id']}, Username: {mt['username']}, Total: {mt['total_messages_today']}")
print("\nSIGNALS:")
for s in mt["signals"]:
    print(f"  [{s['time']}] (ID: {s['id']}): {s['text']}")

print("\nSAMPLE / ALL MESSAGES:")
for sm in mt.get("sample_messages", []):
    print("  ---")
    print(sm)
