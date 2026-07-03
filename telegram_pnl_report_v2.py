import json
import re
from pathlib import Path
from collections import defaultdict

# ---------- CONFIG ----------
HISTORY_FILE = r"C:\\anlyzeforex\\forextele\\telegram_history_90days.json"
CHANNELS_FILE_1 = r"C:\\anlyzeforex\\forextele\\telegram_channels_list.txt"
CHANNELS_FILE_2 = r"C:\\anlyzeforex\\forextele\\telegram_channels_list2.txt"

# Output files
FOREX_REPORT = r"C:\\anlyzeforex\\forextele\\forex_pnl_report.md"
CRYPTO_REPORT = r"C:\\anlyzeforex\\forextele\\crypto_pnl_report.md"

# Position sizing
FOREX_LOT = 0.01          # 0.01 standard lot = 1,000 units
CRYPTO_LOT_USD = 10       # $10 exposure per signal
LEVERAGE = 5

# ---------- HELPERS ----------
def load_channels(path):
    """Parse a channel list file and return a dict {chat_id: name}"""
    mapping = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Expected: -1001234567890 | Channel Name
            parts = line.split('|')
            if len(parts) != 2:
                continue
            chat_id = parts[0].strip().lstrip('-')
            name = parts[1].strip()
            mapping[chat_id] = name
    return mapping

# Load channel metadata from both lists
channel_name_map = {}
channel_name_map.update(load_channels(CHANNELS_FILE_1))
channel_name_map.update(load_channels(CHANNELS_FILE_2))

# Regex to capture BUY/SELL, symbol, optional price
SIGNAL_RE = re.compile(r"\b(?P<action>BUY|SELL)\s+(?P<symbol>[A-Z0-9/]{2,10})(?:\s+(?P<price>\d+(?:\.\d+)?))?", re.IGNORECASE)
TP_RE = re.compile(r"TP\s*[:=]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
SL_RE = re.compile(r"SL\s*[:=]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)

def classify_asset(symbol: str, channel_name: str) -> str:
    """Return 'forex' or 'crypto' based on symbol pattern and channel name heuristics"""
    sym = symbol.upper()
    # Pure heuristic – if symbol contains a slash it is likely forex pair
    if '/' in sym:
        return 'forex'
    # Check known crypto tickers set
    crypto_tokens = {"BTC", "ETH", "USDT", "XRP", "ADA", "DOT", "SOL", "DOGE", "LTC", "BCH", "XAU", "XAG"}
    if any(tok in sym for tok in crypto_tokens):
        return 'crypto'
    # Fallback to channel name cues
    name_up = channel_name.upper()
    if any(word in name_up for word in ["CRYPTO", "BTC", "ETH", "COIN", "TOKEN", "BINANCE"]):
        return 'crypto'
    if any(word in name_up for word in ["FOREX", "FX", "GOLD", "SILVER", "XAU", "XAG", "DOLLAR", "EURO", "YEN"]):
        return 'forex'
    # Default to crypto (most channels we care about)
    return 'crypto'

def compute_profit(action: str, entry: float, tp: float | None, sl: float | None, asset: str) -> float:
    """Calculate profit for a single trade.
    Uses TP if present, otherwise SL. If neither, profit is 0.
    """
    target = tp if tp is not None else sl
    if target is None:
        return 0.0
    price_diff = (target - entry) if action.upper() == "BUY" else (entry - target)
    if asset == "forex":
        # Approximation: 1 pip = 0.0001, we multiply raw diff by 1000 (since 0.01 lot = 1,000 units)
        profit = price_diff * 1000 * FOREX_LOT * LEVERAGE
    else:
        # Crypto: Fixed USD exposure * leverage, position size = (exposure*leverage)/entry
        position_units = (CRYPTO_LOT_USD * LEVERAGE) / entry
        profit = price_diff * position_units
    return profit

# ---------- PROCESS HISTORY ----------
forex_results = defaultdict(list)   # chat_id -> list of profits
crypto_results = defaultdict(list)

with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    msgs = json.load(f)

for msg in msgs:
    chat_id = str(msg.get("channel_id"))
    txt = msg.get("text")
    if not isinstance(txt, str):
        continue
    m = SIGNAL_RE.search(txt)
    if not m:
        continue
    action = m.group("action").upper()
    symbol = m.group("symbol").upper()
    price_str = m.group("price")
    if price_str is None:
        continue  # cannot compute without entry price
    entry_price = float(price_str)
    tp_match = TP_RE.search(txt)
    sl_match = SL_RE.search(txt)
    tp = float(tp_match.group(1)) if tp_match else None
    sl = float(sl_match.group(1)) if sl_match else None
    channel_name = channel_name_map.get(chat_id, "")
    asset_type = classify_asset(symbol, channel_name)
    profit = compute_profit(action, entry_price, tp, sl, asset_type)
    if asset_type == "forex":
        forex_results[chat_id].append(profit)
    else:
        crypto_results[chat_id].append(profit)

# ---------- WRITE REPORTS ----------
def write_report(file_path: str, data: dict, asset_label: str):
    lines = [f"# {asset_label} P&L Report (Lot = 0.01 Forex, $10 Crypto, 5x Leverage)", ""]
    for cid, profits in sorted(data.items(), key=lambda x: sum(x[1]), reverse=True):
        total = sum(profits)
        name = channel_name_map.get(cid, "Unknown")
        lines.append(f"- **{cid}** | {name} | Signals: {len(profits)} | P&L: ${total:,.2f}")
    Path(file_path).write_text("\n".join(lines), encoding="utf-8")

write_report(FOREX_REPORT, forex_results, "Forex")
write_report(CRYPTO_REPORT, crypto_results, "Crypto")

print("Reports generated:")
print(FOREX_REPORT)
print(CRYPTO_REPORT)
