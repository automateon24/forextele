import datetime
from pathlib import Path
import json
import MetaTrader5 as mt5
import pandas as pd
from collections import defaultdict

BASE_DIR = Path(r"C:\anlyzeforex\forextele")

def run_analysis():
    mt5.initialize()
    acct = mt5.account_info()
    print("=" * 80)
    print(f"📊 LIVE ACCOUNT OVERVIEW (XM Global #{acct.login})")
    print(f"Balance: ${acct.balance:.2f} | Equity: ${acct.equity:.2f} | Floating Profit: ${acct.profit:.2f}")
    print("=" * 80)

    # 1. Open Positions
    open_pos = mt5.positions_get()
    print(f"\n--- [1] ACTIVE OPEN POSITIONS ({len(open_pos) if open_pos else 0}) ---")
    if open_pos:
        for p in open_pos:
            p_type = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
            print(f"  Ticket #{p.ticket} | {p_type} {p.volume} {p.symbol} @ {p.price_open:.2f} | Current: {p.price_current:.2f} | SL: {p.sl:.2f} | TP: {p.tp:.2f} | Profit: ${p.profit:.2f} | Comment: {p.comment}")

    # 2. Closed Deals since Sep 23 18:00 UTC (When new rule was deployed)
    start_time = datetime.datetime(2026, 9, 23, 12, 0, 0) # Covers from Sep 23 afternoon
    end_time = datetime.datetime(2026, 9, 26, 23, 59, 59)
    
    deals = mt5.history_deals_get(start_time, end_time)
    if not deals:
        print("No deals found in history.")
        return

    # Group deals by position_id
    pos_deals = defaultdict(list)
    for d in deals:
        if d.position_id:
            pos_deals[d.position_id].append(d)

    completed_positions = []
    for pos_id, d_list in pos_deals.items():
        in_deal = None
        out_deals = []
        for d in d_list:
            if d.entry == mt5.DEAL_ENTRY_IN:
                in_deal = d
            elif d.entry in (mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT, mt5.DEAL_ENTRY_OUT_BY):
                out_deals.append(d)
        
        if in_deal and out_deals:
            total_profit = sum(od.profit + od.swap + od.commission for od in out_deals)
            # volume
            vol = in_deal.volume
            sym = in_deal.symbol
            p_type = "BUY" if in_deal.type == mt5.DEAL_TYPE_BUY else "SELL"
            open_time = datetime.datetime.fromtimestamp(in_deal.time)
            close_time = datetime.datetime.fromtimestamp(max(od.time for od in out_deals))
            comment = in_deal.comment or out_deals[-1].comment or ""
            open_price = in_deal.price
            close_price = out_deals[-1].price
            
            # channel extraction from comment
            chan = comment.strip("[]") if comment else "Direct/Manual"
            
            completed_positions.append({
                "pos_id": pos_id,
                "symbol": sym,
                "type": p_type,
                "volume": vol,
                "open_time": open_time,
                "close_time": close_time,
                "open_price": open_price,
                "close_price": close_price,
                "net_profit": total_profit,
                "channel": chan,
                "comment": comment
            })

    df = pd.DataFrame(completed_positions)
    print(f"\n--- [2] COMPLETED TRADES SINCE DEPLOYMENT: {len(df)} Trades ---")
    if not df.empty:
        total_pnl = df["net_profit"].sum()
        wins = df[df["net_profit"] > 0]
        losses = df[df["net_profit"] < 0]
        breakevens = df[df["net_profit"] == 0]
        win_rate = (len(wins) / len(df)) * 100 if len(df) > 0 else 0
        
        print(f"Total Net PnL: ${total_pnl:.2f}")
        print(f"Win Count: {len(wins)} | Loss Count: {len(losses)} | Breakeven Count: {len(breakevens)}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Gross Profit: ${wins['net_profit'].sum():.2f} | Gross Loss: ${losses['net_profit'].sum():.2f}")
        profit_factor = abs(wins['net_profit'].sum() / losses['net_profit'].sum()) if losses['net_profit'].sum() != 0 else 999.0
        print(f"Profit Factor: {profit_factor:.2f}")

        # Channel Breakdown
        print("\n--- [3] CHANNEL PERFORMANCE BREAKDOWN ---")
        chan_stats = []
        for chan, grp in df.groupby("channel"):
            c_wins = len(grp[grp["net_profit"] > 0])
            c_losses = len(grp[grp["net_profit"] < 0])
            c_total = len(grp)
            c_pnl = grp["net_profit"].sum()
            c_wr = (c_wins / c_total) * 100 if c_total > 0 else 0
            best_t = grp["net_profit"].max()
            worst_t = grp["net_profit"].min()
            chan_stats.append({
                "Channel": chan,
                "Trades": c_total,
                "Wins": c_wins,
                "Losses": c_losses,
                "Win Rate %": round(c_wr, 1),
                "Net PnL ($)": round(c_pnl, 2),
                "Best ($)": round(best_t, 2),
                "Worst ($)": round(worst_t, 2)
            })
        
        df_chan = pd.DataFrame(chan_stats).sort_values(by="Net PnL ($)", ascending=False)
        print(df_chan.to_string(index=False))

        # Counter Trade Analysis (Same symbol, opposite directions near each other)
        print("\n--- [4] OPPOSING / COUNTER TRADES ANALYSIS ---")
        df_sorted = df.sort_values(by="open_time")
        for i in range(len(df_sorted) - 1):
            t1 = df_sorted.iloc[i]
            t2 = df_sorted.iloc[i+1]
            time_diff = (t2["open_time"] - t1["open_time"]).total_seconds() / 60.0
            if t1["symbol"] == t2["symbol"] and t1["type"] != t2["type"] and time_diff <= 120:
                print(f"⚠️ Counter Trade Detected ({time_diff:.1f} mins apart):")
                print(f"   Trade 1: #{t1['pos_id']} {t1['type']} {t1['symbol']} by [{t1['channel']}] @ {t1['open_price']} (PnL: ${t1['net_profit']:.2f})")
                print(f"   Trade 2: #{t2['pos_id']} {t2['type']} {t2['symbol']} by [{t2['channel']}] @ {t2['open_price']} (PnL: ${t2['net_profit']:.2f})")

    # 3. AI Learning Knowledge Base Inspection
    kb_path = BASE_DIR / "data" / "trade_learning_knowledge_base.jsonl"
    print(f"\n--- [5] AI LEARNING KNOWLEDGE BASE ({kb_path.name}) ---")
    if kb_path.exists():
        lines = [json.loads(l) for l in kb_path.read_text(encoding="utf-8").strip().splitlines() if l.strip()]
        print(f"Total Logged Trades in Knowledge Base: {len(lines)}")
        
        # Hypothesis breakdown
        hypo_counts = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        session_counts = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        
        for r in lines:
            ctx = r.get("market_context", {})
            h = ctx.get("hypothesis", "UNKNOWN")
            sess = ctx.get("session", "UNKNOWN")
            pnl = r.get("pnl_usd", 0.0)
            outcome = r.get("outcome", "")
            
            hypo_counts[h]["count"] += 1
            hypo_counts[h]["pnl"] += pnl
            if outcome == "WIN" or pnl > 0:
                hypo_counts[h]["wins"] += 1
            elif outcome == "LOSS" or pnl < 0:
                hypo_counts[h]["losses"] += 1
                
            session_counts[sess]["count"] += 1
            session_counts[sess]["pnl"] += pnl
            if outcome == "WIN" or pnl > 0:
                session_counts[sess]["wins"] += 1
            elif outcome == "LOSS" or pnl < 0:
                session_counts[sess]["losses"] += 1

        print("\nSMC Hypothesis Performance:")
        for h, data in sorted(hypo_counts.items(), key=lambda x: x[1]["pnl"], reverse=True):
            wr = (data["wins"] / data["count"]) * 100 if data["count"] > 0 else 0
            print(f"  {h:<45} | Setups: {data['count']:<3} | Wins: {data['wins']:<2} | Losses: {data['losses']:<2} | WR: {wr:4.1f}% | Net PnL: ${data['pnl']:+6.2f}")

        print("\nSession Performance:")
        for sess, data in sorted(session_counts.items(), key=lambda x: x[1]["pnl"], reverse=True):
            wr = (data["wins"] / data["count"]) * 100 if data["count"] > 0 else 0
            print(f"  {sess:<25} | Setups: {data['count']:<3} | Wins: {data['wins']:<2} | Losses: {data['losses']:<2} | WR: {wr:4.1f}% | Net PnL: ${data['pnl']:+6.2f}")

if __name__ == "__main__":
    run_analysis()
