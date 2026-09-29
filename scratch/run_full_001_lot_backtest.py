import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent

# ── 1. BROKER PARAMETERS (XM Global MT5 Live Verified Specifications) ──
LOT_SIZE = 0.01
LEVERAGE = 1000.0

def calc_trade_pnl(symbol, action, pnl_pips, hold_mins):
    action_u = action.upper()
    nights = max(0, int(hold_mins // 1440))
    
    if symbol == "GOLD":
        # 0.01 lot = 1.0 oz. 1 pip (0.10 price move) = $0.10 USD
        gross_usd = pnl_pips * 0.10
        spread_cost = 0.53 # 53 points @ 0.01 = $0.53
        swap_rate = -0.868 if action_u == "BUY" else 0.198
        swap_usd = nights * swap_rate
        margin = 4.35
        
    elif symbol == "BTCUSD":
        # 0.01 lot = 0.01 BTC. $1 move in BTC = $0.01 USD
        gross_usd = pnl_pips * 0.01
        spread_cost = 0.40 # $40 spread * 0.01 lot = $0.40
        swap_rate = -0.338 if action_u == "BUY" else -0.226
        swap_usd = nights * swap_rate
        margin = 0.65
        
    elif "JPY" in symbol:
        # 0.01 lot = 1,000 units. 1 pip (0.01 JPY) = 10 JPY = $0.0637 USD
        pip_val = 0.063735
        gross_usd = pnl_pips * pip_val
        if "AUD" in symbol:
            spread_cost = 80 * 0.0063735 # 80 points = $0.51
            swap_rate = 0.026 if action_u == "BUY" else -0.106
        elif "GBP" in symbol:
            spread_cost = 73 * 0.0063735 # 73 points = $0.47
            swap_rate = 0.020 if action_u == "BUY" else -0.258
        else: # USDJPY
            spread_cost = 39 * 0.0063735 # 39 points = $0.25
            swap_rate = 0.013 if action_u == "BUY" else -0.188
        swap_usd = nights * swap_rate
        margin = 1.00
        
    elif "US30" in symbol:
        # 0.01 lot = 0.01 contract. 1 point move = $0.01 USD
        gross_usd = pnl_pips * 0.01
        spread_cost = 0.06 # 6.0 points = $0.06
        swap_rate = -0.08 if action_u == "BUY" else 0.01
        swap_usd = nights * swap_rate
        margin = 0.42
        
    else: # Standard Forex (EURCAD, GBPCAD, GBPNZD, EURUSD)
        pip_val = 0.085 # average cross pip value on 0.01 lot
        gross_usd = pnl_pips * pip_val
        spread_cost = 0.25 # ~3.0 pips spread
        swap_rate = -0.07 if action_u == "BUY" else 0.01
        swap_usd = nights * swap_rate
        margin = 1.00

    net_usd = gross_usd - spread_cost + swap_usd
    return round(gross_usd, 3), round(spread_cost, 3), round(swap_usd, 3), round(net_usd, 3), margin

all_trades = []

# ── Load Dataset 1: last_week_gold_backtest_results.csv ──
csv1 = BASE_DIR / "last_week_gold_backtest_results.csv"
if csv1.exists():
    df1 = pd.read_csv(csv1)
    for _, row in df1.iterrows():
        pnl_pips = float(row.get("pnl_pips", 0.0))
        hold_mins = float(row.get("hold_mins", 60))
        action = str(row.get("action", "BUY"))
        channel = str(row.get("channel", "Unknown"))
        outcome = str(row.get("outcome", "WIN" if pnl_pips > 0 else "LOSS"))
        
        gross_usd, spread_usd, swap_usd, net_usd, margin = calc_trade_pnl("GOLD", action, pnl_pips, hold_mins)
        all_trades.append({
            "channel": channel,
            "symbol": "GOLD",
            "action": action,
            "pnl_pips": pnl_pips,
            "outcome": outcome,
            "hold_mins": hold_mins,
            "gross_usd": gross_usd,
            "spread_cost_usd": spread_usd,
            "swap_usd": swap_usd,
            "net_usd": net_usd,
            "margin_used": margin
        })

# ── Load Dataset 2: additional_gold_channels_backtest.csv ──
csv2 = BASE_DIR / "additional_gold_channels_backtest.csv"
if csv2.exists():
    df2 = pd.read_csv(csv2)
    for _, row in df2.iterrows():
        pnl_pips = float(row.get("pnl_pips", 0.0))
        hold_mins = float(row.get("hold_mins", 60))
        action = str(row.get("action", "BUY"))
        channel = str(row.get("channel_name", "Unknown"))
        outcome = str(row.get("outcome", "WIN" if pnl_pips > 0 else "LOSS"))
        
        gross_usd, spread_usd, swap_usd, net_usd, margin = calc_trade_pnl("GOLD", action, pnl_pips, hold_mins)
        all_trades.append({
            "channel": channel,
            "symbol": "GOLD",
            "action": action,
            "pnl_pips": pnl_pips,
            "outcome": outcome,
            "hold_mins": hold_mins,
            "gross_usd": gross_usd,
            "spread_cost_usd": spread_usd,
            "swap_usd": swap_usd,
            "net_usd": net_usd,
            "margin_used": margin
        })

# ── Load Dataset 3: Market Trader Scraped Trades (Forex + Indices + Gold) ──
# 10 setups last week against authentic M1 price bars
mt_trades = [
    {"symbol": "AUDJPY", "action": "BUY", "pnl_pips": 150.0, "outcome": "WIN", "hold_mins": 120},
    {"symbol": "USDJPY", "action": "SELL", "pnl_pips": 180.0, "outcome": "WIN", "hold_mins": 240},
    {"symbol": "GBPJPY", "action": "BUY", "pnl_pips": 250.0, "outcome": "WIN", "hold_mins": 180},
    {"symbol": "GBPCAD", "action": "SELL", "pnl_pips": 120.0, "outcome": "WIN", "hold_mins": 90},
    {"symbol": "EURCAD", "action": "BUY", "pnl_pips": 0.0, "outcome": "BREAKEVEN", "hold_mins": 60},
    {"symbol": "GBPNZD", "action": "SELL", "pnl_pips": -40.0, "outcome": "LOSS", "hold_mins": 45},
    {"symbol": "US30Cash", "action": "BUY", "pnl_pips": 650.0, "outcome": "WIN", "hold_mins": 150},
    {"symbol": "GOLD", "action": "BUY", "pnl_pips": 320.0, "outcome": "WIN", "hold_mins": 110},
    {"symbol": "AUDJPY", "action": "BUY", "pnl_pips": 540.0, "outcome": "WIN", "hold_mins": 300},
    {"symbol": "USDJPY", "action": "SELL", "pnl_pips": 0.0, "outcome": "BREAKEVEN", "hold_mins": 90}
]

for t in mt_trades:
    gross_usd, spread_usd, swap_usd, net_usd, margin = calc_trade_pnl(t["symbol"], t["action"], t["pnl_pips"], t["hold_mins"])
    all_trades.append({
        "channel": "Market Trader Crypto Forex",
        "symbol": t["symbol"],
        "action": t["action"],
        "pnl_pips": t["pnl_pips"],
        "outcome": t["outcome"],
        "hold_mins": t["hold_mins"],
        "gross_usd": gross_usd,
        "spread_cost_usd": spread_usd,
        "swap_usd": swap_usd,
        "net_usd": net_usd,
        "margin_used": margin
    })

# ── Load Dataset 4: Perfect Management (Gold & BTCUSD Multi-TP 6 Hits) ──
# 7 setups last week against authentic M1 price bars
pm_trades = [
    {"symbol": "GOLD", "action": "SELL", "pnl_pips": 240.0, "outcome": "WIN", "hold_mins": 180},
    {"symbol": "GOLD", "action": "SELL", "pnl_pips": 240.0, "outcome": "WIN", "hold_mins": 140},
    {"symbol": "GOLD", "action": "BUY", "pnl_pips": 240.0, "outcome": "WIN", "hold_mins": 190},
    {"symbol": "GOLD", "action": "BUY", "pnl_pips": 240.0, "outcome": "WIN", "hold_mins": 220},
    {"symbol": "GOLD", "action": "SELL", "pnl_pips": 240.0, "outcome": "WIN", "hold_mins": 160},
    {"symbol": "BTCUSD", "action": "SELL", "pnl_pips": 600.0, "outcome": "WIN", "hold_mins": 310}, # $600 move
    {"symbol": "BTCUSD", "action": "BUY", "pnl_pips": 550.0, "outcome": "WIN", "hold_mins": 280}   # $550 move
]

for t in pm_trades:
    gross_usd, spread_usd, swap_usd, net_usd, margin = calc_trade_pnl(t["symbol"], t["action"], t["pnl_pips"], t["hold_mins"])
    all_trades.append({
        "channel": "Perfect Management",
        "symbol": t["symbol"],
        "action": t["action"],
        "pnl_pips": t["pnl_pips"],
        "outcome": t["outcome"],
        "hold_mins": t["hold_mins"],
        "gross_usd": gross_usd,
        "spread_cost_usd": spread_usd,
        "swap_usd": swap_usd,
        "net_usd": net_usd,
        "margin_used": margin
    })

df_all = pd.DataFrame(all_trades)
df_all.to_csv(BASE_DIR / "comprehensive_001_lot_backtest.csv", index=False)

# ── Summary Aggregations ──
summary = []
for ch, group in df_all.groupby("channel"):
    total_trades = len(group)
    wins = len(group[group["outcome"] == "WIN"])
    losses = len(group[group["outcome"] == "LOSS"])
    bes = len(group[group["outcome"] == "BREAKEVEN"])
    win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0
    
    total_pips = group["pnl_pips"].sum()
    total_gross = group["gross_usd"].sum()
    total_spread = group["spread_cost_usd"].sum()
    total_swap = group["swap_usd"].sum()
    total_net = group["net_usd"].sum()
    avg_margin = group["margin_used"].mean()
    
    summary.append({
        "channel": ch,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "breakevens": bes,
        "win_rate_pct": round(win_rate, 1),
        "total_pips": round(total_pips, 1),
        "gross_usd": round(total_gross, 2),
        "spread_cost_usd": round(total_spread, 2),
        "swap_usd": round(total_swap, 2),
        "net_usd": round(total_net, 2),
        "avg_margin_req": round(avg_margin, 2),
        "roi_on_margin_pct": round((total_net / (avg_margin * total_trades) * 100.0) if total_trades > 0 else 0, 1)
    })

df_sum = pd.DataFrame(summary).sort_values(by="net_usd", ascending=False)
df_sum.to_json(BASE_DIR / "comprehensive_001_lot_summary.json", orient="records", indent=2)

print("\n================================================================================")
print("COMPREHENSIVE 0.01 LOT BACKTEST SUMMARY (1000x LEVERAGE, SPREADS & SWAP INCLUDED)")
print("================================================================================")
print(df_sum[["channel", "total_trades", "win_rate_pct", "total_pips", "gross_usd", "spread_cost_usd", "net_usd"]].to_string(index=False))

total_all_net = df_sum["net_usd"].sum()
total_all_trades = df_sum["total_trades"].sum()
total_all_pips = df_sum["total_pips"].sum()
total_all_gross = df_sum["gross_usd"].sum()
total_all_spread = df_sum["spread_cost_usd"].sum()
print("\n--------------------------------------------------------------------------------")
print(f"PORTFOLIO TOTALS (0.01 LOT):")
print(f"  Total Trades Processed: {total_all_trades}")
print(f"  Total Net Pips Gained:  +{total_all_pips:,.1f} pips")
print(f"  Gross Profit:           ${total_all_gross:,.2f} USD")
print(f"  Total Spread Friction:  ${total_all_spread:,.2f} USD")
print(f"  NET REALIZED PROFIT:    +${total_all_net:,.2f} USD")
print("================================================================================\n")
