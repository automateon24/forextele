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
from_48h = now_utc - timedelta(hours=48)

acc = mt5.account_info()
print(f"=== ACCOUNT STATUS ===")
print(f"Login: {acc.login} ({acc.company})")
print(f"Balance: ${acc.balance:,.2f}")
print(f"Equity: ${acc.equity:,.2f}")
print(f"Floating Profit: ${acc.profit:,.2f}")
print(f"Free Margin: ${acc.margin_free:,.2f} (Level: {acc.margin_level}%)")

# Open positions
positions_open = mt5.positions_get()
print(f"\n=== CURRENT OPEN POSITIONS ({len(positions_open) if positions_open else 0}) ===")
if positions_open:
    for p in positions_open:
        p_type = "BUY" if p.type == 0 else "SELL"
        print(f"Ticket #{p.ticket} | {p.symbol} {p_type} {p.volume} lot @ {p.price_open:.2f} -> Current: {p.price_current:.2f} | SL: {p.sl:.2f}, TP: {p.tp:.2f} | Profit: ${p.profit:+.2f} | Magic: {p.magic} | Comment: {p.comment}")

# Closed deals in last 48h
deals = mt5.history_deals_get(from_48h, now_utc)
print(f"\n=== 48-HOUR CLOSED DEALS AUDIT (Since {from_48h.strftime('%Y-%m-%d %H:%M:%S UTC')}) ===")
print(f"Total deal records: {len(deals) if deals else 0}")

# Group deals by position_id
pos_map = defaultdict(list)
for d in (deals or []):
    pos_map[d.position_id].append(d)

closed_positions = []
for pos_id, d_list in pos_map.items():
    # To get accurate entry and exit, query full history of this position
    full_history = mt5.history_deals_get(position=pos_id)
    if not full_history:
        full_history = d_list
    
    entries = [d for d in full_history if d.entry == 0]
    exits = [d for d in full_history if d.entry in (1, 3)] # 1=out, 3=out by close-by
    
    if not entries:
        continue
    if not exits:
        continue # Still open
        
    entry_d = entries[0]
    exit_d = exits[-1]
    
    # Check if exit happened within the 48h window
    exit_time = datetime.fromtimestamp(exit_d.time, tz=timezone.utc)
    if exit_time < from_48h:
        continue
        
    pos_profit = sum(d.profit for d in full_history)
    pos_swap = sum(d.swap for d in full_history)
    pos_comm = sum(d.commission for d in full_history)
    pos_net = pos_profit + pos_swap + pos_comm
    
    p_type = "BUY" if entry_d.type == 0 else "SELL"
    
    closed_positions.append({
        "pos_id": pos_id,
        "symbol": entry_d.symbol,
        "type": p_type,
        "volume": entry_d.volume,
        "price_in": entry_d.price,
        "price_out": exit_d.price,
        "profit": pos_profit,
        "swap": pos_swap,
        "comm": pos_comm,
        "net": pos_net,
        "magic": entry_d.magic,
        "comment": entry_d.comment,
        "time_in": datetime.fromtimestamp(entry_d.time, tz=timezone.utc),
        "time_out": exit_time
    })

print(f"Total Unique Closed Positions in 48h: {len(closed_positions)}")

# High-level stats
total_net = sum(p["net"] for p in closed_positions)
gross_win = sum(p["net"] for p in closed_positions if p["net"] > 0)
gross_loss = sum(p["net"] for p in closed_positions if p["net"] < 0)
wins = [p for p in closed_positions if p["net"] > 0]
losses = [p for p in closed_positions if p["net"] < 0]
be = [p for p in closed_positions if p["net"] == 0]

print(f"Net Realized PnL: ${total_net:+.2f}")
print(f"Gross Profit: ${gross_win:+.2f} | Gross Loss: ${gross_loss:+.2f}")
print(f"Win Rate: {len(wins)}W / {len(losses)}L ({len(wins)/len(closed_positions)*100 if closed_positions else 0:.1f}%)")

# Segment by Magic Number
by_source = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "net": 0.0, "gross_win": 0.0, "gross_loss": 0.0})
for p in closed_positions:
    m = p["magic"]
    if m == 999001:
        src = "Autonomous AI Scanner (Magic 999001)"
    elif m == 888888:
        src = "Market Trader VIP (Magic 888888)"
    elif m == 786786:
        src = "Perfect Management (Magic 786786)"
    elif m == 777777:
        src = "Telegram VIP Channels (Magic 777777)"
    else:
        src = f"Other (Magic {m})"
        
    by_source[src]["count"] += 1
    if p["net"] > 0:
        by_source[src]["wins"] += 1
        by_source[src]["gross_win"] += p["net"]
    elif p["net"] < 0:
        by_source[src]["losses"] += 1
        by_source[src]["gross_loss"] += p["net"]
    by_source[src]["net"] += p["net"]

print(f"\n=== BREAKDOWN BY ENGINE / MAGIC NUMBER ===")
for src, st in sorted(by_source.items(), key=lambda x: x[1]["net"], reverse=True):
    wr = st["wins"] / st["count"] * 100 if st["count"] else 0
    print(f"{src:42} | Trades: {st['count']:3} | {st['wins']}W / {st['losses']}L ({wr:4.1f}%) | Net: ${st['net']:+8.2f} (Win: +${st['gross_win']:.2f}, Loss: -${abs(st['gross_loss']):.2f})")

# Segment Autonomous AI Scanner by Symbol and Direction
print(f"\n=== AUTONOMOUS AI SCANNER DETAILED AUDIT (Magic 999001) ===")
ai_trades = [p for p in closed_positions if p["magic"] == 999001]
ai_by_sym_dir = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "net": 0.0, "gross_win": 0.0, "gross_loss": 0.0})
for p in ai_trades:
    key = f"{p['symbol']} {p['type']}"
    ai_by_sym_dir[key]["count"] += 1
    if p["net"] > 0:
        ai_by_sym_dir[key]["wins"] += 1
        ai_by_sym_dir[key]["gross_win"] += p["net"]
    else:
        ai_by_sym_dir[key]["losses"] += 1
        ai_by_sym_dir[key]["gross_loss"] += p["net"]
    ai_by_sym_dir[key]["net"] += p["net"]

for key, st in sorted(ai_by_sym_dir.items(), key=lambda x: x[1]["net"], reverse=True):
    wr = st["wins"] / st["count"] * 100 if st["count"] else 0
    print(f"AI {key:14} | Trades: {st['count']:2} | {st['wins']}W / {st['losses']}L ({wr:4.1f}%) | Net: ${st['net']:+8.2f} (Win: +${st['gross_win']:.2f}, Loss: -${abs(st['gross_loss']):.2f})")

# Segment Telegram Channels by Comment/Channel
print(f"\n=== TELEGRAM CHANNELS AUDIT (Magic 777777 / 888888 / 786786) ===")
tg_trades = [p for p in closed_positions if p["magic"] != 999001]
tg_by_chan = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "net": 0.0, "gross_win": 0.0, "gross_loss": 0.0, "symbols": set()})

for p in tg_trades:
    cmt = (p["comment"] or "").strip().replace("[", "").replace("]", "")
    m = p["magic"]
    if m == 888888 or "market trader" in cmt.lower():
        chan = "Market Trader Crypto Forex"
    elif m == 786786 or "perfect management" in cmt.lower():
        chan = "Perfect Management"
    elif cmt:
        chan = cmt
    else:
        chan = f"Unknown Magic {m}"
        
    tg_by_chan[chan]["count"] += 1
    tg_by_chan[chan]["symbols"].add(p["symbol"])
    if p["net"] > 0:
        tg_by_chan[chan]["wins"] += 1
        tg_by_chan[chan]["gross_win"] += p["net"]
    else:
        tg_by_chan[chan]["losses"] += 1
        tg_by_chan[chan]["gross_loss"] += p["net"]
    tg_by_chan[chan]["net"] += p["net"]

for chan, st in sorted(tg_by_chan.items(), key=lambda x: x[1]["net"], reverse=True):
    wr = st["wins"] / st["count"] * 100 if st["count"] else 0
    syms = ",".join(st["symbols"])
    print(f"{chan:28} ({syms:12}) | Trades: {st['count']:2} | {st['wins']}W / {st['losses']}L ({wr:4.1f}%) | Net: ${st['net']:+8.2f} (Win: +${st['gross_win']:.2f}, Loss: -${abs(st['gross_loss']):.2f})")

# Check Gold Macro price movement over 48h
rates = mt5.copy_rates_from_pos("GOLD", mt5.TIMEFRAME_H1, 0, 48)
if rates is not None and len(rates) > 0:
    high_48 = max(r['high'] for r in rates)
    low_48 = min(r['low'] for r in rates)
    open_48 = rates[0]['open']
    close_48 = rates[-1]['close']
    drop = close_48 - open_48
    range_48 = high_48 - low_48
    print(f"\n=== GOLD (XAUUSD) 48-HOUR MACRO ACTION ===")
    print(f"Open: {open_48:.2f} | High: {high_48:.2f} | Low: {low_48:.2f} | Current: {close_48:.2f}")
    print(f"Total Fall: {drop:+.2f} points ({drop*10:+.1f} pips) | Total Range: {range_48:.2f} points ({range_48*10:.1f} pips)")

mt5.shutdown()
