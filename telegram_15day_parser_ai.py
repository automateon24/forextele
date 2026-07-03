import json
import re
from pathlib import Path

HISTORY_FILE = r"C:\\anlyzeforex\\forextele\\telegram_history_15days.json"
REPORT_FILE  = r"C:\\anlyzeforex\\forextele\\telegram_verified_15days_report.md"

# Known crypto / forex symbols (case-insensitive)
CRYPTO_TICKERS = {
    "BTC", "ETH", "USDT", "BCH", "LTC", "XRP", "ADA", "DOT",
    "SOL", "DOGE", "XAU", "XAG", "XAUUSD", "XAGUSD", "GOLD"
}
# Common forex pairs (slash format)
FOREX_PAIRS = {
    "EUR/USD", "USD/EUR", "USD/JPY", "JPY/USD",
    "GBP/USD", "USD/GBP", "AUD/USD", "USD/AUD",
    "NZD/USD", "USD/NZD", "CAD/USD", "USD/CAD",
    "CHF/USD", "USD/CHF", "XAU/USD", "USD/XAU"
}
# Anything that should be ignored (equity / index symbols)
EXCLUDE_TOKENS = {"NIFTY", "BANKNIFTY", "NIFTY50", "NIFTYNEXT", "INDEX"}

# Regex patterns
SIGNAL_RE = re.compile(r"\b(?P<action>BUY|SELL)\s+(?P<symbol>[A-Z0-9/]{2,10})\b(?:\s+@?\s*(?P<price>\d+(?:\.\d+)?))?", re.IGNORECASE)
TP_RE    = re.compile(r"TP\s*[:=]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
SL_RE    = re.compile(r"SL\s*[:=]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)

def is_crypto_or_forex(symbol: str) -> bool:
    """Return True if symbol looks like crypto/forex and not excluded."""
    sym = symbol.upper()
    if sym in EXCLUDE_TOKENS:
        return False
    if sym in CRYPTO_TICKERS:
        return True
    if "/" in sym:
        left, right = sym.split("/", 1)
        if left in CRYPTO_TICKERS or right in CRYPTO_TICKERS:
            return True
        if sym in FOREX_PAIRS:
            return True
    return False

def load_history():
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_signals(messages):
    signals = []
    for msg in messages:
        text = msg.get("text")
        if not isinstance(text, str):
            continue
        m = SIGNAL_RE.search(text)
        if not m:
            continue
        symbol = m.group("symbol").upper()
        if not is_crypto_or_forex(symbol):
            continue
        
        # Map XAUUSD / XAU to XMGlobal's GOLD symbol
        if symbol in ["XAUUSD", "XAU", "XAU/USD", "GOLD"]:
            symbol = "GOLD"
            
        action = m.group("action").upper()
        price = m.group("price")
        entry = float(price) if price else None
        tp_match = TP_RE.search(text)
        sl_match = SL_RE.search(text)
        tp = float(tp_match.group(1)) if tp_match else None
        sl = float(sl_match.group(1)) if sl_match else None
        signals.append({
            "date": msg.get("date", "N/A"),
            "action": action,
            "symbol": symbol,
            "entry": entry,
            "tp": tp,
            "sl": sl,
        })
    return signals

def generate_report(signals):
    total = len(signals)
    by_symbol = {}
    for s in signals:
        sym = s["symbol"]
        by_symbol.setdefault(sym, 0)
        by_symbol[sym] += 1
    lines = [
        "# 🤖 AI‑Free 15‑Day Crypto/Forex Backtest Report",
        "",
        f"**Total extracted signals:** {total}",
        "",
        "## Signals by Symbol",
    ]
    for sym, cnt in sorted(by_symbol.items(), key=lambda x: -x[1]):
        lines.append(f"- {sym}: {cnt}")
    lines.append("")
    lines.append("## Detailed Signal List")
    for i, s in enumerate(signals, 1):
        date = s["date"][:10] if s["date"] != "N/A" else "N/A"
        line = f"{i}. {date} – {s['action']} {s['symbol']}"
        if s["entry"] is not None:
            line += f" @ {s['entry']}"
        if s["tp"]:
            line += f", TP {s['tp']}"
        if s["sl"]:
            line += f", SL {s['sl']}"
        lines.append(line)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Report written to {REPORT_FILE}")

if __name__ == "__main__":
    msgs = load_history()
    sigs = parse_signals(msgs)
    generate_report(sigs)
