import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HISTORY_FILE = r"C:\\anlyzeforex\\forextele\\telegram_history_90days.json"
CHANNELS_FILE_1 = r"C:\\anlyzeforex\\forextele\\telegram_channels_list.txt"
CHANNELS_FILE_2 = r"C:\\anlyzeforex\\forextele\\telegram_channels_list2.txt"
OUTPUT_FILE = r"C:\\anlyzeforex\\forextele\\active_crypto_forex_channels.md"

# ---------------------------------------------------------------------
# Helpers to load channel mappings (chat_id -> name)
def load_channel_mapping(path):
    mapping = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('-') is False:
                continue
            # Expected format: -1001234567890 | Channel Name
            parts = line.split('|')
            if len(parts) != 2:
                continue
            chat_id = parts[0].strip().lstrip('-')
            name = parts[1].strip()
            mapping[chat_id] = name
    return mapping

channel_map = {}
channel_map.update(load_channel_mapping(CHANNELS_FILE_1))
channel_map.update(load_channel_mapping(CHANNELS_FILE_2))

# ---------------------------------------------------------------------
# Signal detection (same logic as the parser)
CRYPTO_TICKERS = {"BTC", "ETH", "USDT", "BCH", "LTC", "XRP", "ADA", "DOT",
                  "SOL", "DOGE", "XAU", "XAG", "XAUUSD", "XAGUSD"}
FOREX_PAIRS = {"EUR/USD", "USD/EUR", "USD/JPY", "JPY/USD",
               "GBP/USD", "USD/GBP", "AUD/USD", "USD/AUD",
               "NZD/USD", "USD/NZD", "CAD/USD", "USD/CAD",
               "CHF/USD", "USD/CHF", "XAU/USD", "USD/XAU"}
EXCLUDE_TOKENS = {"NIFTY", "BANKNIFTY", "NIFTY50", "NIFTYNEXT", "INDEX"}
EXCLUDE_NAMES = {"BINOMO", "QUOTEX", "BINARY", "BINARY OPTION"}

SIGNAL_RE = re.compile(r"\b(?P<action>BUY|SELL)\s+(?P<symbol>[A-Z0-9/]{2,10})\b", re.IGNORECASE)

def is_crypto_or_forex(symbol: str) -> bool:
    sym = symbol.upper()
    if sym in EXCLUDE_TOKENS:
        return False
    if sym in CRYPTO_TICKERS:
        return True
    if '/' in sym:
        left, right = sym.split('/', 1)
        if left in CRYPTO_TICKERS or right in CRYPTO_TICKERS:
            return True
        if sym in FOREX_PAIRS:
            return True
    return False

# ---------------------------------------------------------------------
# Parse history and collect channel -> set of dates where a signal appears
channel_dates = defaultdict(set)
with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    messages = json.load(f)

for msg in messages:
    chat_id = str(msg.get('channel_id'))
    text = msg.get('text')
    date_str = msg.get('date')
    if not isinstance(text, str) or not date_str:
        continue
    # Quick skip for binary/quotex channel names if we already know them
    name = channel_map.get(chat_id, "").upper()
    if any(x in name for x in EXCLUDE_NAMES):
        continue
    m = SIGNAL_RE.search(text)
    if not m:
        continue
    if not is_crypto_or_forex(m.group('symbol')):
        continue
    # Extract just the date part (YYYY-MM-DD)
    date_part = date_str.split('T')[0]
    channel_dates[chat_id].add(date_part)

# Keep channels with signals on at least two distinct days
active_channels = {cid: dates for cid, dates in channel_dates.items() if len(dates) >= 2}

# Classify into Crypto vs Forex based on channel name heuristics
crypto_channels = []
forex_channels = []
for cid, dates in active_channels.items():
    name = channel_map.get(cid, "Unknown")
    name_up = name.upper()
    # Simple classification rules
    if any(kw in name_up for kw in ["CRYPTO", "BTC", "ETH", "BINANCE", "COIN", "TOKEN", "SCALP"]):
        crypto_channels.append((cid, name, sorted(dates)))
    elif any(kw in name_up for kw in ["FOREX", "FX", "XAU", "GOLD", "SILVER", "DOLLAR", "EURO", "YEN"]):
        forex_channels.append((cid, name, sorted(dates)))
    else:
        # Default to crypto if contains typical crypto tickers
        if any(t in name_up for t in ["BTC", "ETH", "COIN"]):
            crypto_channels.append((cid, name, sorted(dates)))
        else:
            forex_channels.append((cid, name, sorted(dates)))

# ---------------------------------------------------------------------
# Write markdown report
with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    out.write("# Active Crypto & Forex Channels (≥2 days with signals)\n\n")
    out.write("## Crypto Channels\n\n")
    for cid, name, ds in sorted(crypto_channels, key=lambda x: x[1]):
        out.write(f"- **{cid}** | {name} | Active on: {', '.join(ds)}\n")
    out.write("\n## Forex Channels\n\n")
    for cid, name, ds in sorted(forex_channels, key=lambda x: x[1]):
        out.write(f"- **{cid}** | {name} | Active on: {', '.join(ds)}\n")

print(f"Report written to {OUTPUT_FILE}")
