import re
from pathlib import Path
import json

BASE_DIR = Path(__file__).parent.parent
CH_LIST_1 = BASE_DIR / "telegram_channels_list.txt"
CH_LIST_2 = BASE_DIR / "telegram_channels_list2.txt"

def load_channels(file_path, account_name):
    channels = []
    if not file_path.exists():
        return channels
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.match(r'^(-?[0-9]+)\s*\|\s*(.*)$', line.strip())
            if m:
                cid = int(m.group(1))
                title = m.group(2).strip()
                channels.append({"id": cid, "title": title, "account": account_name})
    return channels

acc1_chs = load_channels(CH_LIST_1, "Account 1")
acc2_chs = load_channels(CH_LIST_2, "Account 2 (Active)")

all_chs = acc2_chs + acc1_chs

vip_targets = [
    # Discovered Winners
    "Market Trader", "Perfect Management", "Forex with karol", "ALTO FX", "XAUUSD GOLD MASTER", "Swift Gold Forex",
    "JOSEFINA TRADER", "SureShot GOLD", "Profitway", "RIAOGOLDFOREX", "Grade Profit forex", "PipXpert", "Rocky Gold fx",
    "The Forex Blueprint", "Pero | Forex", "GOLD PRO TRADER",
    
    # User Channels
    "MrGoldenWay Trader", "XAUUSD Signal 99%", "Gold Trade Signals", "Vault Gold Forex™", "GOLDEN STAR SIGNAL",
    "Gold Best Signal Group", "BEST FX XAUUSD GOLD TRADER", "MIKE GOLD MASTER", "Gold Trade Experts",
    "XAUUSD EA & XAUUSD Killer", "XAUUSD PIPS KILLER", "Best Gold EA Auto Trade", "FOREX GOLD TEAM Tr",
    "GOLD KILLER", "King of gold", "GoldSignals.io", "GOLD Copy Trading", "Gold VIP",
    "Saviour Gold EA", "HFT GOLD TRADING", "FOREX GOLD SIGNAL"
]

matched = []
seen_ids = set()

for target in vip_targets:
    target_clean = re.sub(r'[^a-zA-Z0-9]', '', target.lower())
    found = False
    for ch in all_chs:
        ch_clean = re.sub(r'[^a-zA-Z0-9]', '', ch["title"].lower())
        # check partial match
        if (target_clean in ch_clean) or (len(target_clean) > 6 and target_clean[:7] in ch_clean) or (target.lower() in ch["title"].lower()):
            if ch["id"] not in seen_ids:
                seen_ids.add(ch["id"])
                clean_title = ch["title"].encode('ascii', 'ignore').decode('ascii')
                matched.append({
                    "target_name": target,
                    "matched_title": clean_title,
                    "id": ch["id"],
                    "account": ch["account"]
                })
            found = True
            break
            
    if not found:
        if "market trader" in target.lower():
            matched.append({"target_name": target, "matched_title": "Market Trader Crypto Forex", "id": -1002350799273, "account": "Account 2 (Active)"})
        elif "perfect management" in target.lower():
            matched.append({"target_name": target, "matched_title": "Perfect Management", "id": -1001509806486, "account": "Account 2 (Active)"})
        else:
            # Let's search loosely
            loose_match = None
            words = [w for w in target.lower().split() if len(w) > 3 and w not in ("gold", "forex", "trader", "signal")]
            if words:
                for ch in all_chs:
                    if all(w in ch["title"].lower() for w in words):
                        loose_match = ch
                        break
            if loose_match:
                clean_title = loose_match["title"].encode('ascii', 'ignore').decode('ascii')
                matched.append({"target_name": target, "matched_title": clean_title, "id": loose_match["id"], "account": loose_match["account"]})
            else:
                matched.append({"target_name": target, "matched_title": target, "id": "Dynamic Event Catch", "account": "Account 1 / 2"})

out_path = BASE_DIR / "matched_monitored_channels.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(matched, f, indent=2)

for m in matched:
    safe_title = m['matched_title'][:35]
    print(f"{m['id']} | {safe_title} | {m['account']}")
