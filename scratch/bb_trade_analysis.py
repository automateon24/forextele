"""
Breakout Boss Deep Trade Analysis — AI Pattern Audit
Pulls every BB trade, enriches with direction/hour/day/outcome and prints a summary
"""
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
from collections import defaultdict

mt5.initialize()

from_date = datetime(2026, 9, 29, 0, 0, 0, tzinfo=timezone.utc)
to_date   = datetime.now(timezone.utc) + timedelta(days=1)

deals = mt5.history_deals_get(from_date, to_date) or []
closed = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT and d.symbol]

BB_MAGICS = {555000, 555001, 555002, 555003, 555004, 555555}
bb = [d for d in closed if d.magic in BB_MAGICS]

print(f"Total BB closed deals: {len(bb)}\n")

# Per-direction analysis
dir_map = defaultdict(lambda: dict(pnl=0.0, t=0, w=0))
for d in bb:
    direction = 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL'
    dir_map[direction]['pnl'] += d.profit + d.swap
    dir_map[direction]['t']   += 1
    if (d.profit+d.swap) > 0:
        dir_map[direction]['w'] += 1

print("=== BY DIRECTION ===")
for dr, v in dir_map.items():
    wr = v['w']/v['t']*100 if v['t'] else 0
    print(f"  {dr}: {v['t']} trades | {v['w']}W | WR:{wr:.1f}% | Net:{v['pnl']:+.2f}")

# Per-hour analysis
hour_map = defaultdict(lambda: dict(pnl=0.0, t=0, w=0))
for d in bb:
    hr = datetime.fromtimestamp(d.time, tz=timezone.utc).hour
    hour_map[hr]['pnl'] += d.profit + d.swap
    hour_map[hr]['t']   += 1
    if (d.profit+d.swap) > 0:
        hour_map[hr]['w'] += 1

print("\n=== BY HOUR (UTC) ===")
for hr in sorted(hour_map):
    v = hour_map[hr]
    wr = v['w']/v['t']*100 if v['t'] else 0
    bar = "+" * v['w'] + "-" * (v['t']-v['w'])
    print(f"  {hr:02d}:00  {v['t']:>3} trades | WR:{wr:>5.1f}% | Net:{v['pnl']:>+8.2f}  [{bar}]")

# Per-day
day_map = defaultdict(lambda: dict(pnl=0.0, t=0, w=0))
for d in bb:
    dt = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime("%Y-%m-%d")
    day_map[dt]['pnl'] += d.profit + d.swap
    day_map[dt]['t']   += 1
    if (d.profit+d.swap) > 0:
        day_map[dt]['w'] += 1

print("\n=== BY DAY ===")
for dt in sorted(day_map):
    v = day_map[dt]
    wr = v['w']/v['t']*100 if v['t'] else 0
    print(f"  {dt} | {v['t']:>3} trades | {v['w']}W | WR:{wr:>5.1f}% | Net:{v['pnl']:>+8.2f}")

# Avg win vs avg loss
wins  = [d.profit+d.swap for d in bb if (d.profit+d.swap) > 0]
losses= [abs(d.profit+d.swap) for d in bb if (d.profit+d.swap) <= 0]
avg_w = sum(wins)/len(wins) if wins else 0
avg_l = sum(losses)/len(losses) if losses else 0
rr    = avg_w/avg_l if avg_l else 0

print(f"\n=== R:R ANALYSIS ===")
print(f"  Avg Win   : ${avg_w:.2f}")
print(f"  Avg Loss  : ${avg_l:.2f}")
print(f"  Actual R:R: {rr:.2f}  (need >2.0 to be profitable at 28.7% WR)")
print(f"  Min WR needed at this R:R: {1/(1+rr)*100:.1f}%")

# Top individual wins and losses
print("\n=== TOP 5 WINS ===")
top_w = sorted(bb, key=lambda d: d.profit+d.swap, reverse=True)[:5]
for d in top_w:
    dt = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime("%m-%d %H:%M")
    dr = 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL'
    print(f"  #{d.ticket} | {dt} UTC | {dr} {d.volume}lot | {d.comment[:30]} | P&L: {d.profit+d.swap:+.2f}")

print("\n=== TOP 5 LOSSES ===")
top_l = sorted(bb, key=lambda d: d.profit+d.swap)[:5]
for d in top_l:
    dt = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime("%m-%d %H:%M")
    dr = 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL'
    print(f"  #{d.ticket} | {dt} UTC | {dr} {d.volume}lot | {d.comment[:30]} | P&L: {d.profit+d.swap:+.2f}")

mt5.shutdown()
