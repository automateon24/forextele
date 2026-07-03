import json
import re
from pathlib import Path
from collections import defaultdict

# Files
HISTORY_FILE = r"C:\\anlyzeforex\\forextele\\telegram_history_90days.json"
ACTIVE_CHANNELS_FILE = r"C:\\anlyzeforex\\forextele\\active_crypto_forex_channels.md"
OUTPUT_FILE = r"C:\\anlyzeforex\\forextele\\channel_pnl_report.md"

# Load active channel IDs from the markdown report
active_ids = set()
with open(ACTIVE_CHANNELS_FILE, "r", encoding="utf-8") as f:
    for line in f:
        m = re.search(r"\*\*([-\d]+)\*\*", line)
        if m:
            active_ids.add(m.group(1))

# Regex to detect BUY/SELL signals (same as before)
SIGNAL_RE = re.compile(r"\b(?P<action>BUY|SELL)\s+(?P<symbol>[A-Z0-9/]{2,10})(?:\s+(?P<price>\d+(?:\.\d+)?))?", re.IGNORECASE)
TP_RE = re.compile(r"TP\s*[:=]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
SL_RE = re.compile(r"SL\s*[:=]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)

# Settings
FOREX_LOT = 0.01          # standard lot = 100,000 units -> 0.01 = 1,000 units
CRYPTO_LOT_USD = 10       # fixed USD exposure per signal
LEVERAGE = 5

# Helper to compute profit
def compute_profit(signal):
    action = signal["action"]
    entry = signal["entry"]
    tp = signal.get("tp")
    sl = signal.get("sl")
    symbol = signal["symbol"]
    # Determine asset class
    is_forex = "/" in symbol or any(cur in symbol for cur in ["USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "XAU"])
    # Use TP if available, otherwise SL; if neither, profit = 0
    target_price = tp if tp is not None else sl
    if target_price is None:
        return 0.0
    price_diff = (target_price - entry) if action == "BUY" else (entry - target_price)
    if is_forex:
        # Approximation: 1 pip = 0.0001 for most pairs; we use raw price diff * lot * 1000 * leverage
        profit = price_diff * 1000 * FOREX_LOT * LEVERAGE
    else:
        # Crypto: Fixed USD exposure per signal (CRYPTO_LOT_USD) with leverage
        # Position size (units) = (exposure * leverage) / entry price
        position_units = (CRYPTO_LOT_USD * LEVERAGE) / entry
        profit = price_diff * position_units
    return profit

# Parse history
channel_signals = defaultdict(list)
with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    msgs = json.load(f)

for msg in msgs:
    chat_id = str(msg.get("channel_id"))
    if chat_id not in active_ids:
        continue
    text = msg.get("text")
    if not isinstance(text, str):
        continue
    m = SIGNAL_RE.search(text)
    if not m:
        continue
    symbol = m.group("symbol").upper()
    action = m.group("action").upper()
    entry = float(m.group("price")) if m.group("price") else None
    if entry is None:
        continue
    tp_match = TP_RE.search(text)
    sl_match = SL_RE.search(text)
    tp = float(tp_match.group(1)) if tp_match else None
    sl = float(sl_match.group(1)) if sl_match else None
    signal = {"symbol": symbol, "action": action, "entry": entry, "tp": tp, "sl": sl}
    channel_signals[chat_id].append(signal)

# Compute PnL per channel
report_lines = ["# Channel P&L Report (Lot = 0.01 Forex, $10 Crypto, 5x Leverage)", ""]
for cid, signals in channel_signals.items():
    total = 0.0
    for s in signals:
        total += compute_profit(s)
    report_lines.append(f"- **{cid}** | Signals: {len(signals)} | P&L: ${total:,.2f}")

with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    out.write("\n".join(report_lines))

print(f"Report written to {OUTPUT_FILE}")
