import json, re, os

HISTORY_FILE = r"C:\\anlyzeforex\\forextele\\telegram_history_15days.json"
REPORT_FILE = r"C:\\anlyzeforex\\forextele\\telegram_verified_15days_report.md"

# Simple regex patterns for signals
SIGNAL_REGEX = re.compile(r"\b(BUY|SELL)\s+([A-Z]{2,5})\s+@?\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
TP_REGEX = re.compile(r"TP\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
SL_REGEX = re.compile(r"SL\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)

def load_history():
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def parse_signals(messages):
    signals = []
    for msg in messages:
        text = msg.get("text", "")
        if not isinstance(text, str):
            continue
        # Find primary BUY/SELL entry
        m = SIGNAL_REGEX.search(text)
        if m:
            action, symbol, entry_price = m.groups()
            # Find optional TP/SL in same message
            tp_match = TP_REGEX.search(text)
            sl_match = SL_REGEX.search(text)
            tp = tp_match.group(1) if tp_match else None
            sl = sl_match.group(1) if sl_match else None
            signals.append({
                "action": action.upper(),
                "symbol": symbol.upper(),
                "entry": float(entry_price),
                "tp": float(tp) if tp else None,
                "sl": float(sl) if sl else None,
                "date": msg.get("date")
            })
    return signals

def generate_report(signals):
    total = len(signals)
    symbols = {}
    for s in signals:
        sym = s["symbol"]
        symbols.setdefault(sym, 0)
        symbols[sym] += 1
    lines = []
    lines.append("# 🤖 AI‑Free 15‑Day Telegram Backtest Report")
    lines.append("")
    lines.append(f"**Total extracted signals:** {total}")
    lines.append("")
    lines.append("## Signals by Symbol")
    for sym, cnt in sorted(symbols.items(), key=lambda x: -x[1]):
        lines.append(f"- {sym}: {cnt}")
    lines.append("")
    lines.append("## Detailed Signal List")
    for i, s in enumerate(signals, 1):
        line = f"{i}. {s['date'][:10] if s['date'] else 'N/A'} – {s['action']} {s['symbol']} @ {s['entry']}"
        if s['tp']:
            line += f", TP {s['tp']}"
        if s['sl']:
            line += f", SL {s['sl']}"
        lines.append(line)
    # Write report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Report written to {REPORT_FILE}")

if __name__ == "__main__":
    msgs = load_history()
    sigs = parse_signals(msgs)
    generate_report(sigs)
