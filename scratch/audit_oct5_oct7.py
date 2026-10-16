import MetaTrader5 as mt5
from datetime import datetime, timezone

if not mt5.initialize():
    print("MT5 init failed")
    exit(1)

from_dt = datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc)
to_dt = datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc)
deals = mt5.history_deals_get(from_dt, to_dt) or []

closed = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
wins = [d for d in closed if d.profit > 0]
losses = [d for d in closed if d.profit < 0]
breakeven = [d for d in closed if d.profit == 0]

net_pnl = sum(d.profit + d.swap for d in closed)
win_pnl = sum(d.profit for d in wins)
loss_pnl = abs(sum(d.profit for d in losses))
pf = (win_pnl / loss_pnl) if loss_pnl > 0 else 999.0
wr = (len(wins) / len(closed) * 100) if closed else 0.0

print(f"Total closed trades (Oct 5-7): {len(closed)}")
print(f"Wins: {len(wins)} | Losses: {len(losses)} | Breakeven: {len(breakeven)}")
print(f"Win Rate: {wr:.1f}% | Profit Factor: {pf:.2f} | Net PnL: ${net_pnl:+,.2f}")

# Breakdown by magic number
by_magic = {}
for d in closed:
    m = d.magic
    if m not in by_magic:
        by_magic[m] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "comments": set()}
    by_magic[m]["trades"] += 1
    if d.profit > 0:
        by_magic[m]["wins"] += 1
    elif d.profit < 0:
        by_magic[m]["losses"] += 1
    by_magic[m]["pnl"] += d.profit + d.swap
    if d.comment:
        by_magic[m]["comments"].add(d.comment[:25])

print("\n--- PERFORMANCE BY ENGINE / MAGIC NUMBER ---")
for m, stat in sorted(by_magic.items(), key=lambda x: x[1]["trades"], reverse=True):
    engine_name = "UNKNOWN"
    if m == 777777:
        engine_name = "Telegram VIP Signals (Account 1)"
    elif m == 888001:
        engine_name = "Telegram VIP Signals (Account 2)"
    elif m in [555000, 555001, 555002, 555003, 555004, 555555]:
        engine_name = f"BreakoutBoss v2 (Model {m})"
    elif m == 999001:
        engine_name = "Autonomous SMC AI Scanner"
    elif m == 0:
        engine_name = "Manual / Unassigned Magic"
    
    m_wr = (stat["wins"] / stat["trades"] * 100) if stat["trades"] else 0.0
    print(f"Magic {m} [{engine_name}]: {stat['trades']} trades | WR: {m_wr:.1f}% | Net PnL: ${stat['pnl']:+,.2f} | Samples: {list(stat['comments'])[:3]}")

print("\n--- LAST 20 CLOSED TRADES ---")
for d in closed[-20:]:
    dt = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime("%m-%d %H:%M")
    print(f"{dt} | Magic:{d.magic:<6} | {d.symbol:<6} | Vol:{d.volume:<4.2f} | PnL:${d.profit:+7.2f} | Comm:{d.comment}")

mt5.shutdown()
