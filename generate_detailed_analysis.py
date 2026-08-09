import pandas as pd
import numpy as np
import joblib
import json
import os

print("Starting Deep Dive Analysis...")

# Load Data
df = pd.read_csv("backtest_highres_signals.csv", parse_dates=["time"])
df = df[df["outcome"].isin(["WIN","LOSS","EXPIRED"])].copy()

# Load ML Model
model = joblib.load("final_model_sucess.joblib")
CAT_COLS = ["symbol","strategy","direction","session"]
NUM_COLS = ["hour","weekday","rsi_val","adx_val","atr","sl_pts","tp_pts"]

feats = df[CAT_COLS + NUM_COLS]
probs = model.predict_proba(feats)[:,1]
df["win_prob"] = probs

# Filter like the main report
df = df[df["win_prob"] >= 0.50].copy()

# Constants
CONTRACT_SIZE = {
    "EURUSD":100_000, "GBPUSD":100_000, "AUDUSD":100_000, "USDJPY":100_000,
    "GOLD":100, "SILVER":5000, "BTCUSD":1, "ETHUSD":1,
}
POINT = {
    "EURUSD":0.00001,"GBPUSD":0.00001,"USDJPY":0.001,"AUDUSD":0.00001,
    "GOLD":0.01,"SILVER":0.001,"BTCUSD":0.01,"ETHUSD":0.001,
}

# Use flat 1.0 lot to see raw native performance
def compute_raw_pnl(row):
    sym = row["symbol"]
    pt  = POINT.get(sym, 0.00001)
    cs  = CONTRACT_SIZE.get(sym, 100_000)
    raw = row["pnl_pts"] * pt * cs
    if sym == "USDJPY":
        return raw / 150.0
    return raw

df["pnl_usd"] = df.apply(compute_raw_pnl, axis=1)
df["date"] = df["time"].dt.date
df["month"] = df["time"].dt.to_period("M")

# --- Helper to calculate Drawdown ---
def calc_dd(group_df, time_col):
    time_grouped = group_df.groupby(time_col)["pnl_usd"].sum().cumsum()
    peak = time_grouped.cummax()
    dd = (time_grouped - peak)
    return dd.min()

# 1. Strategy Breakdown
strat_stats = []
for strat, group in df.groupby("strategy"):
    trades = len(group)
    wins = (group["outcome"] == "WIN").sum()
    win_rate = (wins / trades) * 100
    pnl = group["pnl_usd"].sum()
    
    # Drawdowns (using cumsum of PNL to find max absolute USD drawdown)
    daily_dd = calc_dd(group, "date")
    monthly_dd = calc_dd(group, "month")
    
    strat_stats.append({
        "Strategy": strat,
        "Trades": trades,
        "Win%": f"{win_rate:.1f}%",
        "Net P&L (USD)": pnl,
        "Max Daily DD (USD)": daily_dd,
        "Max Monthly DD (USD)": monthly_dd
    })

strat_df = pd.DataFrame(strat_stats).sort_values("Net P&L (USD)", ascending=False)

# 2. Pair Breakdown
pair_stats = []
for sym, group in df.groupby("symbol"):
    trades = len(group)
    wins = (group["outcome"] == "WIN").sum()
    win_rate = (wins / trades) * 100
    pnl = group["pnl_usd"].sum()
    
    daily_dd = calc_dd(group, "date")
    monthly_dd = calc_dd(group, "month")
    
    # Best hours
    hourly = group.groupby("hour").apply(lambda x: (x["outcome"]=="WIN").sum() / len(x) if len(x)>0 else 0, include_groups=False)
    best_hour = hourly.idxmax() if not hourly.empty else "N/A"
    
    pair_stats.append({
        "Symbol": sym,
        "Trades": trades,
        "Win%": f"{win_rate:.1f}%",
        "Net P&L (USD)": pnl,
        "Best Hour (UTC)": f"{best_hour}:00",
        "Max Daily DD (USD)": daily_dd,
        "Max Monthly DD (USD)": monthly_dd
    })

pair_df = pd.DataFrame(pair_stats).sort_values("Net P&L (USD)", ascending=False)

# 3. Generate Markdown Artifact
md_content = "# 📊 1-Year Deep Dive Analysis (Flat 1.0 Lot Base)\\n\\n"
md_content += "*Note: This report simulates a fixed 1.0 Lot size across all trades to calculate absolute USD Drawdowns without compounding distortion.*\\n\\n"

md_content += "## 🏆 1. Strategy Performance & Drawdown Analysis\\n\\n"
md_content += "| Strategy | Trades | Win Rate | Net P&L | Max Daily DD | Max Monthly DD |\\n"
md_content += "|----------|--------|----------|---------|--------------|----------------|\\n"
for _, row in strat_df.iterrows():
    md_content += f"| {row['Strategy']} | {row['Trades']} | {row['Win%']} | ${row['Net P&L (USD)']:,.2f} | ${row['Max Daily DD (USD)']:,.2f} | ${row['Max Monthly DD (USD)']:,.2f} |\\n"

md_content += "\\n## 💱 2. Pair Performance, Optimal Times & Drawdowns\\n\\n"
md_content += "| Symbol | Trades | Win Rate | Best Hour | Net P&L | Max Daily DD | Max Monthly DD |\\n"
md_content += "|--------|--------|----------|-----------|---------|--------------|----------------|\\n"
for _, row in pair_df.iterrows():
    md_content += f"| {row['Symbol']} | {row['Trades']} | {row['Win%']} | {row['Best Hour (UTC)']} | ${row['Net P&L (USD)']:,.2f} | ${row['Max Daily DD (USD)']:,.2f} | ${row['Max Monthly DD (USD)']:,.2f} |\\n"

# Write Artifact
report_path = os.path.join(os.getcwd(), "detailed_1year_analysis.md")
with open(report_path, "w", encoding='utf-8') as f:
    f.write(md_content)

print(f"Deep Dive Report Generated: {report_path}")
