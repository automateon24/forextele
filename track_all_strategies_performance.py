"""
TRACK ALL STRATEGIES & MODELS PERFORMANCE LEDGER
================================================
Parses MT5 closed deals and live open positions to show exact performance
attributed to each Strategy, Engine, Model, and Channel via Order Comments and Magics.
Resolves original order comments even if broker overwrote deal exit comment with [sl] / [tp].
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import MetaTrader5 as mt5

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
CONFIG_PATH = BASE_DIR / "mt5_config.json"

def classify_trade(comment: str, magic: int) -> tuple:
    """
    Returns (MajorCategory, ModelOrChannelName)
    """
    comment = comment or ""
    
    # 1. Breakout Boss Engine (Magics 555000-555004, 555555)
    if magic in range(555000, 555005) or magic == 555555 or comment.startswith("BB_"):
        if "M0" in comment or magic == 555000:
            return "Breakout Boss", "Model 0 (Baseline Fixed)"
        elif "M1" in comment or magic == 555001:
            return "Breakout Boss", "Model 1 (Step-Ladder)"
        elif "M2" in comment or magic == 555002:
            return "Breakout Boss", "Model 2 (Linear Equity)"
        elif "M3" in comment or magic == 555003:
            return "Breakout Boss", "Model 3 (AI Conviction)"
        elif "M4" in comment or magic == 555004:
            return "Breakout Boss", "Model 4 (Half-Kelly)"
        return "Breakout Boss", "Breakout General"

    # 2. Autonomous SMC & Indian Market Adapted Scanner (Magic 999001)
    if magic == 999001 or "AI_SMC" in comment or "SMC" in comment or "AIO_" in comment:
        if "OVERSOLD" in comment:
            return "AI SMC / Indian Adaptation", "Oversold Liquidity Sweep"
        elif "OVERBOUGHT" in comment:
            return "AI SMC / Indian Adaptation", "Overbought Liquidity Sweep"
        elif "FVG" in comment:
            return "AI SMC / Indian Adaptation", "Fair Value Gap Expansion"
        elif "AIO_DILSE" in comment:
            return "Indian Adapted Strategies", "Dilse Pullback"
        elif "AIO_BOLLINGER" in comment:
            return "Indian Adapted Strategies", "Bollinger Squeeze"
        return "AI SMC Scanner", "Autonomous SMC Scanner"

    # 3. Telegram VIP NLP Channels (Magic 777777 / 888888)
    if magic in (777777, 888888) or comment.startswith("[") or "Tele:" in comment:
        chan_name = comment.replace("[", "").replace("]", "").replace("Tele:", "").strip()
        if not chan_name: chan_name = "VIP Channel"
        return "Telegram VIP NLP", f"Channel: {chan_name[:24]}"

    # 4. Other
    return "Other / Discretionary", f"Manual (Magic {magic})"

def main():
    if not mt5.initialize():
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            mt5.initialize(login=cfg.get("login"), server=cfg.get("server"), password=cfg.get("password"))

    acc = mt5.account_info()
    if not acc:
        print("❌ Could not connect to MT5.")
        return

    print("=" * 85)
    print(f" 🚀 FOREXTELE STRATEGY & COMMENT ATTRIBUTION AUDIT | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f" 💰 Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f} | Free Margin: ${acc.margin_free:,.2f}")
    print("=" * 85)

    # 1. Active Open Positions
    positions = mt5.positions_get()
    print("\n🟢 1. ACTIVE LIVE OPEN POSITIONS (TAGGED WITH REAL-TIME COMMENTS):")
    print("-" * 85)
    if positions:
        for p in positions:
            cat, sub = classify_trade(p.comment, p.magic)
            side = "BUY" if p.type == 0 else "SELL"
            print(f"  • Ticket #{p.ticket} | {p.symbol:<7} {side:<4} {p.volume:.2f} lots @ {p.price_open:.2f}")
            print(f"    SL: {p.sl:.2f} | TP: {p.tp:.2f} | Floating P&L: ${p.profit:+.2f}")
            print(f"    🏷️  Order Comment    : '{p.comment}' (Magic: {p.magic})")
            print(f"    📂  Attributed Engine: {cat} -> {sub}")
            print("-" * 85)
    else:
        print("  (No positions currently open - awaiting market open for Gold/FX)")

    # 2. Historical Closed Deals Performance by Strategy Comment
    now = datetime.now()
    start_time = now - timedelta(days=7) # Past 7 days
    deals = mt5.history_deals_get(start_time, now)

    order_comment_cache = {}
    cat_summary = defaultdict(lambda: {"trades": 0, "wins": 0, "losses": 0, "net_pnl": 0.0})
    model_summary = defaultdict(lambda: {"category": "", "trades": 0, "wins": 0, "losses": 0, "net_pnl": 0.0})

    if deals:
        for d in deals:
            if d.entry == mt5.DEAL_ENTRY_OUT: # Only closed exits
                pnl = d.profit + d.swap + d.commission
                
                # Resolve original comment
                effective_comment = d.comment or ""
                if effective_comment.startswith("[sl") or effective_comment.startswith("[tp") or not effective_comment:
                    pos_id = d.position_id
                    if pos_id not in order_comment_cache:
                        orders = mt5.history_orders_get(ticket=pos_id)
                        if orders and orders[0].comment:
                            order_comment_cache[pos_id] = orders[0].comment
                        else:
                            order_comment_cache[pos_id] = effective_comment
                    effective_comment = order_comment_cache[pos_id]

                cat, sub = classify_trade(effective_comment, d.magic)
                
                # Category aggregation
                cat_summary[cat]["trades"] += 1
                cat_summary[cat]["net_pnl"] += pnl
                if pnl > 0: cat_summary[cat]["wins"] += 1
                else: cat_summary[cat]["losses"] += 1

                # Sub-model aggregation
                model_summary[sub]["category"] = cat
                model_summary[sub]["trades"] += 1
                model_summary[sub]["net_pnl"] += pnl
                if pnl > 0: model_summary[sub]["wins"] += 1
                else: model_summary[sub]["losses"] += 1

    print("\n🏆 2. PERFORMANCE ROLLUP BY ENGINE (LAST 7 DAYS):")
    print("-" * 85)
    print(f"{'Engine / Trading Daemon':<38} | {'Trades':<6} | {'Win Rate':<8} | {'Net P&L ($)':<12}")
    print("-" * 85)
    for cat, s in sorted(cat_summary.items(), key=lambda x: x[1]["net_pnl"], reverse=True):
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        print(f"{cat:<38} | {s['trades']:<6} | {wr:>6.1f}% | ${s['net_pnl']:>+10.2f}")

    print("\n📊 3. DETAILED BREAKDOWN BY MODEL / STRATEGY (TOP PERFORMERS):")
    print("-" * 85)
    print(f"{'Strategy / Model / Channel':<38} | {'Engine':<20} | {'Trades':<6} | {'WR %':<6} | {'Net P&L ($)':<10}")
    print("-" * 85)
    for sub, s in sorted(model_summary.items(), key=lambda x: x[1]["net_pnl"], reverse=True)[:15]:
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        print(f"{sub:<38} | {s['category']:<20} | {s['trades']:<6} | {wr:>5.1f}% | ${s['net_pnl']:>+9.2f}")

    print("=" * 85)

if __name__ == "__main__":
    main()
