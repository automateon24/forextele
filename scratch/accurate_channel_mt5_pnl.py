import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import json
from collections import defaultdict
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

now_utc = datetime.now(timezone.utc)
from_date = datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc)
to_date = now_utc + timedelta(days=1)

deals = mt5.history_deals_get(from_date, to_date)

# Group deals by position_id
positions = defaultdict(list)
for d in deals:
    positions[d.position_id].append(d)

print(f"Total positions today: {len(positions)}")

channel_summary = defaultdict(lambda: {
    "trades": 0, "wins": 0, "losses": 0, "net_pnl": 0.0, 
    "symbols": set(), "details": []
})

for pos_id, pos_deals in positions.items():
    entry_deals = [d for d in pos_deals if d.entry == 0]
    exit_deals = [d for d in pos_deals if d.entry in (1, 3)]
    
    if not entry_deals:
        continue
        
    entry_d = entry_deals[0]
    initial_comment = entry_d.comment or ""
    magic = entry_d.magic
    symbol = entry_d.symbol
    entry_time = datetime.fromtimestamp(entry_d.time, tz=timezone.utc).strftime('%H:%M:%S UTC')
    
    # Calculate position total PnL
    pos_pnl = sum(d.profit + d.swap + d.commission for d in pos_deals)
    
    # Is it closed?
    is_closed = len(exit_deals) > 0
    if not is_closed:
        continue  # only analyze closed trades for PnL
        
    exit_d = exit_deals[-1]
    exit_time = datetime.fromtimestamp(exit_d.time, tz=timezone.utc).strftime('%H:%M:%S UTC')
    
    # Identify channel from entry deal comment or magic
    channel = "Unknown"
    comment_clean = initial_comment.strip()
    
    if magic == 888888 or "market trader" in comment_clean.lower():
        channel = "Market Trader"
    elif magic == 786786 or "perfect" in comment_clean.lower():
        channel = "Perfect Management"
    elif comment_clean:
        channel = comment_clean
    else:
        channel = f"Magic:{magic}"

    channel_summary[channel]["trades"] += 1
    if pos_pnl >= 0:
        channel_summary[channel]["wins"] += 1
    else:
        channel_summary[channel]["losses"] += 1
    channel_summary[channel]["net_pnl"] += pos_pnl
    channel_summary[channel]["symbols"].add(symbol)
    channel_summary[channel]["details"].append({
        "pos_id": pos_id,
        "symbol": symbol,
        "entry_time": entry_time,
        "exit_time": exit_time,
        "volume": entry_d.volume,
        "pnl": round(pos_pnl, 2),
        "entry_comment": comment_clean,
        "exit_comment": exit_d.comment,
        "magic": magic
    })

print(f"\n{'Channel Name':<35} | {'Trades':>6} | {'W/L':>7} | {'Win%':>6} | {'Net PnL ($)':>12}")
print("=" * 75)
total_pnl = 0.0
total_trades = 0
total_wins = 0
total_losses = 0

for ch, data in sorted(channel_summary.items(), key=lambda x: x[1]["net_pnl"]):
    t = data["trades"]
    w = data["wins"]
    l = data["losses"]
    p = data["net_pnl"]
    total_trades += t
    total_wins += w
    total_losses += l
    total_pnl += p
    wp = f"{w/t*100:.1f}%" if t > 0 else "0%"
    print(f"{ch:<35} | {t:>6} | {w:>3}/{l:<3} | {wp:>6} | ${p:>11.2f}")

print("=" * 75)
print(f"{'TOTAL':<35} | {total_trades:>6} | {total_wins:>3}/{total_losses:<3} | {total_wins/total_trades*100:.1f}% | ${total_pnl:>11.2f}\n")

# Detailed trade log by channel
for ch, data in sorted(channel_summary.items(), key=lambda x: x[1]["net_pnl"]):
    print(f"\n--- {ch} (Net: ${data['net_pnl']:.2f}) ---")
    for d in data["details"]:
        print(f"  PosID:{d['pos_id']} | {d['entry_time']} -> {d['exit_time']} | {d['symbol']} {d['volume']} lot | PnL: ${d['pnl']:>6.2f} | Magic: {d['magic']} | Comm: '{d['entry_comment']}' -> '{d['exit_comment']}'")
