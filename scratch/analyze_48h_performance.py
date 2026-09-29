import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
import json
import csv

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
from_48h = datetime(2026, 9, 21, 17, 0, 0, tzinfo=timezone.utc)
to_date = now_utc + timedelta(days=1)

deals = mt5.history_deals_get(from_48h, to_date)
print(f"Total deals in 48h (since Sep 21 17:00 UTC): {len(deals) if deals else 0}")

# Group deals by position_id
positions = defaultdict(list)
for d in (deals or []):
    positions[d.position_id].append(d)

print(f"Total positions in 48h: {len(positions)}")

channel_summary = defaultdict(lambda: {
    "trades": 0, "wins": 0, "losses": 0, "breakevens": 0,
    "gross_profit": 0.0, "swap": 0.0, "net_pnl": 0.0,
    "symbols": set(), "deals": [], "magic_numbers": set()
})

total_net = 0.0
total_trades = 0
total_wins = 0
total_losses = 0

for pos_id, pos_deals in positions.items():
    entry_deals = [d for d in pos_deals if d.entry == 0]
    exit_deals = [d for d in pos_deals if d.entry in (1, 3)]
    
    if not entry_deals:
        # Check if entry deal happened earlier before from_48h
        all_pos_deals = mt5.history_deals_get(position=pos_id)
        if all_pos_deals:
            entry_deals = [d for d in all_pos_deals if d.entry == 0]
            
    if not entry_deals:
        continue
        
    entry_d = entry_deals[0]
    initial_comment = (entry_d.comment or "").strip()
    magic = entry_d.magic
    symbol = entry_d.symbol
    entry_time = datetime.fromtimestamp(entry_d.time, tz=timezone.utc)
    
    # Check if closed
    if not exit_deals:
        continue
        
    exit_d = exit_deals[-1]
    exit_time = datetime.fromtimestamp(exit_d.time, tz=timezone.utc)
    
    # Calculate PnL for this position across all its deals
    pos_profit = sum(d.profit for d in pos_deals)
    pos_swap = sum(d.swap for d in pos_deals)
    pos_comm = sum(d.commission for d in pos_deals)
    pos_net = pos_profit + pos_swap + pos_comm
    
    # Channel identification
    channel = "Unknown"
    comment_clean = initial_comment.replace("[", "").replace("]", "").strip()
    
    if magic == 888888 or "market trader" in initial_comment.lower():
        channel = "Market Trader Crypto Forex"
    elif magic == 786786 or "perfect management" in initial_comment.lower():
        channel = "Perfect Management"
    elif comment_clean:
        channel = comment_clean
    elif magic == 777777:
        channel = "Telegram VIP (Magic 777777)"
    elif magic == 123456:
        channel = "Legacy SMC Algo (Magic 123456)"
    else:
        channel = f"Magic {magic}"
        
    st = channel_summary[channel]
    st["trades"] += 1
    st["magic_numbers"].add(magic)
    st["symbols"].add(symbol)
    st["gross_profit"] += pos_profit
    st["swap"] += pos_swap
    st["net_pnl"] += pos_net
    
    total_trades += 1
    total_net += pos_net
    
    if pos_net > 0.10:
        st["wins"] += 1
        total_wins += 1
        outcome = "WIN"
    elif pos_net < -0.10:
        st["losses"] += 1
        total_losses += 1
        outcome = "LOSS"
    else:
        st["breakevens"] += 1
        outcome = "BREAKEVEN"
        
    st["deals"].append({
        "pos_id": pos_id,
        "symbol": symbol,
        "volume": entry_d.volume,
        "entry_time": entry_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "exit_time": exit_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "net_pnl": round(pos_net, 2),
        "outcome": outcome,
        "magic": magic,
        "entry_comment": initial_comment,
        "exit_comment": exit_d.comment
    })

print(f"\n{'Channel / Strategy Name':<35} | {'Trades':>6} | {'W/BE/L':>9} | {'Win%':>6} | {'Net PnL ($)':>12}")
print("=" * 77)

profitable_channels = []
loss_channels = []
breakeven_channels = []

for ch, st in sorted(channel_summary.items(), key=lambda x: x[1]["net_pnl"], reverse=True):
    t = st["trades"]
    w = st["wins"]
    be = st["breakevens"]
    l = st["losses"]
    p = st["net_pnl"]
    wp = f"{w/t*100:.1f}%" if t > 0 else "0.0%"
    w_str = f"{w}/{be}/{l}"
    print(f"{ch:<35} | {t:>6} | {w_str:>9} | {wp:>6} | ${p:>11.2f}")
    
    if p > 0.05:
        profitable_channels.append((ch, st))
    elif p < -0.05:
        loss_channels.append((ch, st))
    else:
        breakeven_channels.append((ch, st))

print("=" * 77)
win_rate_total = (total_wins / total_trades * 100) if total_trades > 0 else 0
print(f"{'TOTAL REALIZED CLOSED TRADES':<35} | {total_trades:>6} | {total_wins}/{total_trades-total_wins-total_losses}/{total_losses} | {win_rate_total:>5.1f}% | ${total_net:>11.2f}")

print(f"\nSummary of Channel Profitability:")
print(f"  Profitable Channels: {len(profitable_channels)}")
print(f"  Losing Channels:     {len(loss_channels)}")
print(f"  Breakeven Channels:  {len(breakeven_channels)}")

# Save json report
output_data = {
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "period": "Last 48 Hours (2026-09-21 17:00 UTC to 2026-09-23 12:35 UTC)",
    "summary": {
        "total_trades": total_trades,
        "wins": total_wins,
        "losses": total_losses,
        "net_pnl": round(total_net, 2),
        "win_rate": round(win_rate_total, 1),
        "profitable_channels_count": len(profitable_channels),
        "losing_channels_count": len(loss_channels)
    },
    "channels": {ch: {k: (list(v) if isinstance(v, set) else v) for k, v in st.items()} for ch, st in channel_summary.items()}
}

with open(BASE_DIR / "scratch" / "48h_channel_performance.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2, ensure_ascii=False)

print(f"\nReport saved to scratch/48h_channel_performance.json")
