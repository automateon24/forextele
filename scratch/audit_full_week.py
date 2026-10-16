import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta

if not mt5.initialize():
    print("MT5 initialization failed")
    exit(1)

acc = mt5.account_info()
print("=" * 70)
print(f"  FULL WEEK PERFORMANCE AUDIT (OCT 5 - OCT 9, 2026)")
print(f"  Account: {acc.login} | Server: {acc.server} | Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f}")
print("=" * 70)

# Entire week deals
week_start = datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc)
week_end = datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)
fix_timestamp = datetime(2026, 10, 7, 16, 20, tzinfo=timezone.utc)  # When Option 2 & BB fixes were deployed

deals = mt5.history_deals_get(week_start, week_end) or []
closed_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]

def analyze_subset(name, subset_deals):
    wins = [d for d in subset_deals if d.profit > 0]
    losses = [d for d in subset_deals if d.profit < 0]
    be = [d for d in subset_deals if d.profit == 0]
    net_pnl = sum(d.profit + d.swap for d in subset_deals)
    win_pnl = sum(d.profit for d in wins)
    loss_pnl = abs(sum(d.profit for d in losses))
    pf = (win_pnl / loss_pnl) if loss_pnl > 0 else (999.0 if win_pnl > 0 else 1.0)
    wr = (len(wins) / len(subset_deals) * 100) if subset_deals else 0.0
    print(f"\n--- {name} ---")
    print(f"Total Trades: {len(subset_deals)} | Wins: {len(wins)} | Losses: {len(losses)} | Breakeven: {len(be)}")
    print(f"Win Rate: {wr:.1f}% | Profit Factor: {pf:.2f} | Net Realized PnL: ${net_pnl:+,.2f}")
    
    # Engine breakdown
    by_magic = {}
    for d in subset_deals:
        m = d.magic
        if m not in by_magic:
            by_magic[m] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        by_magic[m]["trades"] += 1
        if d.profit > 0:
            by_magic[m]["wins"] += 1
        elif d.profit < 0:
            by_magic[m]["losses"] += 1
        by_magic[m]["pnl"] += d.profit + d.swap

    for m, st in sorted(by_magic.items(), key=lambda x: x[1]["trades"], reverse=True):
        eng = "Unknown"
        if m == 777777: eng = "Telegram VIP (Account 1)"
        elif m == 888001: eng = "Telegram VIP (Account 2)"
        elif m in [555000, 555001, 555002, 555003, 555004, 555555]: eng = f"BreakoutBoss (Model {m})"
        elif m == 999001: eng = "Autonomous SMC AI Scanner"
        elif m == 888888: eng = "Market Trader Engine"
        elif m == 786786: eng = "Perfect Management"
        elif m == 0: eng = "Manual / Unassigned"
        m_wr = (st["wins"] / st["trades"] * 100) if st["trades"] else 0.0
        print(f"  Magic {m:<6} [{eng:<25}]: {st['trades']:>3} trades | WR: {m_wr:>5.1f}% | Net PnL: ${st['pnl']:>+8.2f}")

# 1. Full Week Overview
analyze_subset("FULL WEEK TOTAL (MON OCT 5 - FRI OCT 9)", closed_deals)

# 2. Phase 1: Pre-Fix (Oct 5 00:00 to Oct 7 16:20)
pre_fix = [d for d in closed_deals if datetime.fromtimestamp(d.time, tz=timezone.utc) < fix_timestamp]
analyze_subset("PHASE 1: PRE-FIX CHOP & UNTHROTTLED (OCT 5 - OCT 7 16:20 UTC)", pre_fix)

# 3. Phase 2: Post-Fix (Oct 7 16:20 to Oct 9 Now)
post_fix = [d for d in closed_deals if datetime.fromtimestamp(d.time, tz=timezone.utc) >= fix_timestamp]
analyze_subset("PHASE 2: POST-FIX OPTION 2 + BB 1-TRADE SAFEGUARD (OCT 7 16:20 - OCT 9 NOW)", post_fix)

# 4. Check Current Pending Orders
ords = mt5.orders_get() or []
print(f"\n--- CURRENT PENDING ORDERS ({len(ords)}) ---")
for o in ords:
    o_type = "BUY LIMIT" if o.type == 2 else ("SELL LIMIT" if o.type == 3 else ("BUY STOP" if o.type == 4 else ("SELL STOP" if o.type == 5 else f"TYPE_{o.type}")))
    print(f"  Order #{o.ticket} {o.symbol} {o_type} Vol:{o.volume_current} @ {o.price_open:.2f} (SL: {o.sl:.2f}, TP: {o.tp:.2f}) Magic:{o.magic} Comm:{o.comment}")

# 5. Daily Day-by-Day PnL
print(f"\n--- DAY-BY-DAY NET PNL BREAKDOWN ---")
days = {}
for d in closed_deals:
    dt_day = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime("%Y-%m-%d (%A)")
    if dt_day not in days:
        days[dt_day] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}
    days[dt_day]["trades"] += 1
    if d.profit > 0: days[dt_day]["wins"] += 1
    elif d.profit < 0: days[dt_day]["losses"] += 1
    days[dt_day]["pnl"] += d.profit + d.swap

for day_str, dst in sorted(days.items()):
    d_wr = (dst["wins"] / dst["trades"] * 100) if dst["trades"] else 0.0
    print(f"  {day_str:<22}: {dst['trades']:>3} trades | WR: {d_wr:>5.1f}% | Net PnL: ${dst['pnl']:>+8.2f}")

mt5.shutdown()
