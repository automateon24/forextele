import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
cfg_file = BASE_DIR / "mt5_config.json"
mt5_cfg = json.loads(cfg_file.read_text()) if cfg_file.exists() else {}

if not mt5.initialize(
    login=int(mt5_cfg.get("login", 0)),
    server=mt5_cfg.get("server", ""),
    password=mt5_cfg.get("password", "")
):
    mt5.initialize()

acct = mt5.account_info()
print(f"MT5 Account: {acct.login} | Server: {acct.server}")
print(f"Balance: ${acct.balance:.2f} | Equity: ${acct.equity:.2f}")

now_utc = datetime.now(timezone.utc)
from_date = datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc)
to_date = now_utc + timedelta(days=1)

deals = mt5.history_deals_get(from_date, to_date)
closed_deals = [d for d in deals if d.entry in (1, 3)] if deals else []

total_profit = sum(d.profit for d in closed_deals)
total_comm = sum(d.commission for d in closed_deals)
total_swap = sum(d.swap for d in closed_deals)
net_pnl = total_profit + total_comm + total_swap

print(f"\nCLOSED DEALS TODAY: {len(closed_deals)}")
print(f"Total Profit: ${total_profit:.2f} | Swap: ${total_swap:.2f} | NET PNL: ${net_pnl:.2f}\n")

# Channel map based on magic number and comment
def identify_channel(d):
    magic = d.magic
    comment = d.comment or ""
    if magic == 888888 or "market trader" in comment.lower():
        return "Market Trader"
    elif magic == 786786 or "perfect" in comment.lower():
        return "Perfect Management"
    elif "sureshot" in comment.lower():
        return "SureShot Gold"
    elif "swift" in comment.lower():
        return "Swift Gold Forex"
    elif "vault" in comment.lower():
        return "Vault Gold Forex"
    elif "vijay" in comment.lower():
        return "Vijay Gold Forex"
    elif "riao" in comment.lower():
        return "RIAOGOLDFOREX"
    elif "master" in comment.lower():
        return "XAUUSD GOLD MASTER"
    elif "josefina" in comment.lower():
        return "JOSEFINA TRADER"
    elif "blueprint" in comment.lower():
        return "THE FOREX BLUEPRINT"
    elif "grade" in comment.lower():
        return "Grade Profit forex"
    else:
        return f"Other/Swarm (Magic:{magic}, Comm:{comment})"

from collections import defaultdict
by_channel = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "profit": 0.0, "swap": 0.0, "deals": []})

for d in closed_deals:
    ch = identify_channel(d)
    dt = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime('%H:%M:%S')
    pnl = d.profit + d.swap + d.commission
    by_channel[ch]["count"] += 1
    if pnl >= 0:
        by_channel[ch]["wins"] += 1
    else:
        by_channel[ch]["losses"] += 1
    by_channel[ch]["profit"] += pnl
    by_channel[ch]["deals"].append({
        "ticket": d.ticket,
        "time": dt,
        "symbol": d.symbol,
        "volume": d.volume,
        "profit": round(pnl, 2),
        "comment": d.comment
    })

print(f"{'Channel / Strategy':<32} | {'Deals':>5} | {'W/L':>7} | {'Win%':>6} | {'Net PnL':>10}")
print("-" * 72)
for ch, st in sorted(by_channel.items(), key=lambda x: x[1]["profit"]):
    win_pct = f"{st['wins']/st['count']*100:.1f}%" if st['count'] > 0 else "0.0%"
    print(f"{ch:<32} | {st['count']:>5} | {st['wins']:>3}/{st['losses']:<3} | {win_pct:>6} | ${st['profit']:>9.2f}")

print("\n--- ALL INDIVIDUAL CLOSED DEALS TODAY ---")
for d in closed_deals:
    deal_time = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime('%H:%M:%S UTC')
    pnl = d.profit + d.swap + d.commission
    ch = identify_channel(d)
    print(f"{deal_time} | Ticket:{d.ticket} | {d.symbol:<8} | Vol:{d.volume:<4} | PnL:${pnl:>7.2f} | Ch:{ch:<22} | Comm:'{d.comment}'")
