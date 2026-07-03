import re
from pathlib import Path

# Input channel list files
CHANNELS_FILE_1 = r"C:\\anlyzeforex\\forextele\\telegram_channels_list.txt"
CHANNELS_FILE_2 = r"C:\\anlyzeforex\\forextele\\telegram_channels_list2.txt"

# Output markdown files
CRYPTO_OUT = r"C:\\anlyzeforex\\forextele\\crypto_channels_full.md"
FOREX_OUT = r"C:\\anlyzeforex\\forextele\\forex_channels_full.md"

def load_channels(path):
    mapping = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Expect format: -1001234567890 | Channel Name
            parts = line.split('|')
            if len(parts) != 2:
                continue
            chat_id = parts[0].strip().lstrip('-')
            name = parts[1].strip()
            mapping[chat_id] = name
    return mapping

# Load both channel lists
channels = {}
channels.update(load_channels(CHANNELS_FILE_1))
channels.update(load_channels(CHANNELS_FILE_2))

# Heuristics to classify
crypto_keywords = ["CRYPTO", "BTC", "ETH", "BINANCE", "COIN", "TOKEN", "SCALP", "KRAKEN", "COINBASE", "XRP", "ADA", "DOGE", "SOL", "DOT", "LTC", "BCH"]
forex_keywords = ["FOREX", "FX", "GOLD", "SILVER", "XAU", "XAG", "DOLLAR", "EURO", "YEN", "POUND", "JPY", "AUD", "CAD", "CHF", "GBP", "USD", "PIPS", "SNIPER"]

crypto_channels = []
forex_channels = []
others = []

for cid, name in channels.items():
    name_up = name.upper()
    is_crypto = any(k in name_up for k in crypto_keywords)
    is_forex = any(k in name_up for k in forex_keywords)
    if is_crypto and not is_forex:
        crypto_channels.append((cid, name))
    elif is_forex and not is_crypto:
        forex_channels.append((cid, name))
    else:
        # If both match or none, decide by presence of '/' in name (rare) or fallback to crypto list
        if '/' in name_up:
            forex_channels.append((cid, name))
        else:
            crypto_channels.append((cid, name))

# Write markdown files
with open(CRYPTO_OUT, "w", encoding="utf-8") as f:
    f.write("# Full Crypto Channel List\n\n")
    for cid, name in sorted(crypto_channels, key=lambda x: x[1]):
        f.write(f"- **{cid}** | {name}\n")

with open(FOREX_OUT, "w", encoding="utf-8") as f:
    f.write("# Full Forex Channel List\n\n")
    for cid, name in sorted(forex_channels, key=lambda x: x[1]):
        f.write(f"- **{cid}** | {name}\n")

print("Channel lists written:")
print(CRYPTO_OUT)
print(FOREX_OUT)
