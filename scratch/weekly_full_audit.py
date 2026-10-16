import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from collections import defaultdict

if not mt5.initialize():
    print("Failed to initialize MT5")
    exit(1)

start_dt = datetime(2026, 10, 11, 0, 0, 0)
end_dt = datetime(2026, 10, 17, 23, 59, 59)

deals = mt5.history_deals_get(start_dt, end_dt)
print(f"Total deals in period: {len(deals) if deals else 0}")

# Also fetch all orders to map comments if deal comment is truncated or sl/tp
orders = mt5.history_orders_get(start_dt, end_dt)
order_comments = {}
order_magics = {}
if orders:
    for o in orders:
        order_comments[o.ticket] = o.comment
        order_magics[o.ticket] = o.magic

# Group deals by position_id to get full position round-trips
positions_deals = defaultdict(list)
for d in deals:
    positions_deals[d.position_id].append(d)

print(f"Total unique positions traded: {len(positions_deals)}")

# Inspect engines
engine_stats = defaultdict(lambda: {
    "trades": 0, "wins": 0, "losses": 0, "breakeven": 0,
    "gross_profit": 0.0, "gross_loss": 0.0, "commission": 0.0, "swap": 0.0,
    "net_pnl": 0.0, "symbols": defaultdict(int), "symbols_pnl": defaultdict(float)
})

strategy_stats = defaultdict(lambda: {
    "trades": 0, "wins": 0, "losses": 0,
    "gross_profit": 0.0, "gross_loss": 0.0, "net_pnl": 0.0
})

symbol_stats = defaultdict(lambda: {
    "trades": 0, "wins": 0, "losses": 0,
    "gross_profit": 0.0, "gross_loss": 0.0, "net_pnl": 0.0
})

trade_records = []

for pos_id, d_list in positions_deals.items():
    # Sort deals by time
    d_list = sorted(d_list, key=lambda x: x.time_msc)
    
    in_deals = [d for d in d_list if d.entry == 0]
    out_deals = [d for d in d_list if d.entry == 1]
    
    if not out_deals:
        # Still open position
        continue
    
    # Position closed
    symbol = d_list[0].symbol
    magic = d_list[0].magic
    comment = d_list[0].comment or ""
    
    # Fallback to order comment if deal comment is generic (like sl, tp, so)
    if magic == 0 or comment == "" or comment.startswith("[sl") or comment.startswith("[tp"):
        for d in in_deals:
            if d.order in order_comments and order_comments[d.order]:
                comment = order_comments[d.order]
                magic = order_magics.get(d.order, magic)
                break

    # Sum profit, commission, swap
    tot_profit = sum(d.profit for d in d_list)
    tot_comm = sum(d.commission for d in d_list)
    tot_swap = sum(d.swap for d in d_list)
    net_pnl = tot_profit + tot_comm + tot_swap
    
    open_time = datetime.fromtimestamp(d_list[0].time, tz=timezone.utc)
    close_time = datetime.fromtimestamp(out_deals[-1].time, tz=timezone.utc)
    volume = sum(d.volume for d in in_deals)
    
    # Engine classifier
    engine = "OTHER / UNKNOWN"
    strategy = "OTHER"
    
    comm_upper = comment.upper()
    
    # 1. Breakout Boss (BB)
    if "BREAKOUT" in comm_upper or "BB_" in comm_upper or magic in (111001, 111002, 111003, 111004, 111005, 888100):
        engine = "BREAKOUT BOSS (BB)"
        if "M0" in comm_upper or "FIXED" in comm_upper: strategy = "BB_M0_FIXED"
        elif "M1" in comm_upper or "STEP" in comm_upper: strategy = "BB_M1_STEP_LADDER"
        elif "M2" in comm_upper or "LINEAR" in comm_upper: strategy = "BB_M2_LINEAR"
        elif "M3" in comm_upper or "KELLY" in comm_upper: strategy = "BB_M3_AI_KELLY"
        elif "M4" in comm_upper: strategy = "BB_M4_HALF_KELLY"
        elif "GANN" in comm_upper: strategy = "BB_GANN_HARMONIC"
        else: strategy = "BB_SESSION_BREAKOUT"
        
    # 2. All-In-One (AIO) Quantitative Engine
    elif "AIO_" in comm_upper or magic == 888101:
        engine = "ALL-IN-ONE (AIO) ENGINE"
        if "DILSE" in comm_upper: strategy = "AIO_DILSE_PULLBACK"
        elif "SMC" in comm_upper or "FVG" in comm_upper: strategy = "AIO_SMC_FVG"
        elif "BOLLINGER" in comm_upper or "SQUEEZE" in comm_upper: strategy = "AIO_BOLLINGER_SQUEEZE"
        elif "ORDER_BLOCK" in comm_upper or "OB" in comm_upper: strategy = "AIO_ORDER_BLOCK"
        else: strategy = "AIO_QUANT_GENERAL"
        
    # 3. Autonomous AI Market Scanner
    elif "AI_SCANNER" in comm_upper or "SMC_SCANNER" in comm_upper or magic == 999001:
        engine = "AUTONOMOUS AI SCANNER"
        strategy = "SMC_LIQUIDITY_SWEEP"
        
    # 4. Telegram VIP Swarm
    elif any(k in comm_upper for k in ["TELE", "SWARM", "VIP", "CHANNEL", "SCALPING GOLD", "ZERO", "APEX", "BULLS"]):
        engine = "TELEGRAM VIP SIGNALS"
        strategy = f"TG_{comment[:20]}"
    elif magic in (777001, 777002, 777003, 777100):
        engine = "TELEGRAM VIP SIGNALS"
        strategy = "TG_VIP_SWARM"
    else:
        # Check by comment contents
        if "DILSE" in comm_upper:
            engine = "ALL-IN-ONE (AIO) ENGINE"
            strategy = "AIO_DILSE_PULLBACK"
        elif "FVG" in comm_upper:
            engine = "ALL-IN-ONE (AIO) ENGINE"
            strategy = "AIO_SMC_FVG"
        elif "BREAKOUT" in comm_upper:
            engine = "BREAKOUT BOSS (BB)"
            strategy = "BB_BREAKOUT"
        else:
            engine = "TELEGRAM VIP / SWARM"
            strategy = comment[:25] if comment else f"Magic_{magic}"

    # Update stats
    st = engine_stats[engine]
    st["trades"] += 1
    st["commission"] += tot_comm
    st["swap"] += tot_swap
    st["net_pnl"] += net_pnl
    st["symbols"][symbol] += 1
    st["symbols_pnl"][symbol] += net_pnl
    
    if net_pnl > 0.001:
        st["wins"] += 1
        st["gross_profit"] += net_pnl
    elif net_pnl < -0.001:
        st["losses"] += 1
        st["gross_loss"] += abs(net_pnl)
    else:
        st["breakeven"] += 1

    # Strategy stats
    strat_key = f"{engine} :: {strategy}"
    ss = strategy_stats[strat_key]
    ss["trades"] += 1
    ss["net_pnl"] += net_pnl
    if net_pnl > 0.001:
        ss["wins"] += 1
        ss["gross_profit"] += net_pnl
    elif net_pnl < -0.001:
        ss["losses"] += 1
        ss["gross_loss"] += abs(net_pnl)

    # Symbol stats
    sym_s = symbol_stats[symbol]
    sym_s["trades"] += 1
    sym_s["net_pnl"] += net_pnl
    if net_pnl > 0.001:
        sym_s["wins"] += 1
        sym_s["gross_profit"] += net_pnl
    elif net_pnl < -0.001:
        sym_s["losses"] += 1
        sym_s["gross_loss"] += abs(net_pnl)

    trade_records.append({
        "pos_id": pos_id,
        "symbol": symbol,
        "engine": engine,
        "strategy": strategy,
        "magic": magic,
        "comment": comment,
        "open_time": open_time.strftime("%Y-%m-%d %H:%M"),
        "close_time": close_time.strftime("%Y-%m-%d %H:%M"),
        "volume": volume,
        "net_pnl": round(net_pnl, 2),
        "commission": round(tot_comm, 2),
        "swap": round(tot_swap, 2)
    })

# Output comprehensive report
print("\n" + "="*80)
print(f"📊 WEEKLY PERFORMANCE AUDIT: 2026-10-11 TO 2026-10-17")
print("="*80)

acc = mt5.account_info()
print(f"Account Balance : ${acc.balance:,.2f} USD")
print(f"Account Equity  : ${acc.equity:,.2f} USD")
print(f"Floating PnL    : ${acc.profit:,.2f} USD")
print(f"Free Margin     : ${acc.margin_free:,.2f} USD")
print(f"Margin Level    : {acc.margin_level:.2f}%")

total_closed = len(trade_records)
total_net = sum(t["net_pnl"] for t in trade_records)
total_comm = sum(t["commission"] for t in trade_records)
total_swap = sum(t["swap"] for t in trade_records)
total_wins = sum(1 for t in trade_records if t["net_pnl"] > 0)
total_losses = sum(1 for t in trade_records if t["net_pnl"] < 0)
overall_wr = (total_wins / total_closed * 100) if total_closed else 0.0

print(f"\nTotal Closed Trades: {total_closed} | Wins: {total_wins} | Losses: {total_losses} | Win Rate: {overall_wr:.1f}%")
print(f"Total Net PnL       : ${total_net:+,.2f} USD (Includes ${total_comm:,.2f} Comm, ${total_swap:,.2f} Swap)")

print("\n" + "-"*80)
print("🏆 ENGINE-WISE PERFORMANCE (WHO MADE HOW MUCH LOSS/PROFIT):")
print("-"*80)
print(f"{'Engine':<28} | {'Trades':<6} | {'Wins':<4} | {'Losses':<6} | {'WinRate':<7} | {'Gross Profit':<13} | {'Gross Loss':<12} | {'Net PnL':<12}")
print("-"*95)

sorted_engines = sorted(engine_stats.items(), key=lambda x: x[1]["net_pnl"], reverse=True)
for eng, s in sorted_engines:
    wr = (s['wins'] / s['trades'] * 100) if s['trades'] else 0.0
    print(f"{eng:<28} | {s['trades']:<6} | {s['wins']:<4} | {s['losses']:<6} | {wr:>5.1f}% | ${s['gross_profit']:>10.2f} | ${s['gross_loss']:>9.2f} | ${s['net_pnl']:>+9.2f}")

print("\n" + "-"*80)
print("📈 STRATEGY-WISE DETAILED BREAKDOWN:")
print("-"*80)
sorted_strats = sorted(strategy_stats.items(), key=lambda x: x[1]["net_pnl"], reverse=True)
for strat, s in sorted_strats:
    wr = (s['wins'] / s['trades'] * 100) if s['trades'] else 0.0
    print(f"{strat:<45} | Trades:{s['trades']:<4} | W:{s['wins']:<3} L:{s['losses']:<3} ({wr:4.1f}%) | Net: ${s['net_pnl']:>+8.2f} (GP:${s['gross_profit']:.1f}, GL:${s['gross_loss']:.1f})")

print("\n" + "-"*80)
print("💱 ASSET / SYMBOL-WISE PERFORMANCE:")
print("-"*80)
sorted_syms = sorted(symbol_stats.items(), key=lambda x: x[1]["net_pnl"], reverse=True)
for sym, s in sorted_syms:
    wr = (s['wins'] / s['trades'] * 100) if s['trades'] else 0.0
    print(f"{sym:<10} | Trades:{s['trades']:<4} | W:{s['wins']:<3} L:{s['losses']:<3} ({wr:4.1f}%) | Net: ${s['net_pnl']:>+8.2f} (GP:${s['gross_profit']:.1f}, GL:${s['gross_loss']:.1f})")

# Current open positions
pos = mt5.positions_get()
print("\n" + "-"*80)
print(f"📍 CURRENT OPEN POSITIONS ({len(pos) if pos else 0}):")
print("-"*80)
if pos:
    for p in pos:
        t_str = "BUY" if p.type == 0 else "SELL"
        print(f"Ticket: {p.ticket} | {p.symbol:<7} {t_str:<4} {p.volume:.2f} lots | Open: {p.price_open:<9} Cur: {p.price_current:<9} | PnL: ${p.profit:>+7.2f} | {p.comment}")

mt5.shutdown()
