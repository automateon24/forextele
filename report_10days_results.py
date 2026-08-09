import joblib
import numpy as np
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_DIR    = Path(r"C:\anlyzeforex\forextele")
SIG_CSV     = BASE_DIR / "backtest_highres_signals.csv"
MODEL_PATH  = BASE_DIR / "final_model_sucess.joblib"
REPORT_PATH = BASE_DIR / "ml_10day_backtest_report.md"

CAPITAL     = 10_000.0
BASE_LOT    = 0.02
ML_THRESH   = 0.60

CONTRACT_SIZE = {
    "EURUSD":100_000, "GBPUSD":100_000, "AUDUSD":100_000,
    "USDJPY":100_000/150.0,
    "GOLD":100, "SILVER":5000,
    "BTCUSD":1, "ETHUSD":1,
}

POINT = {
    "EURUSD":0.00001,"GBPUSD":0.00001,"USDJPY":0.001,"AUDUSD":0.00001,
    "GOLD":0.01,"SILVER":0.001,"BTCUSD":0.01,"ETHUSD":0.001,
}

CAT_COLS = ["symbol","strategy","direction","session"]
NUM_COLS = ["hour","weekday","rsi_val","adx_val","atr","sl_pts","tp_pts"]

def compute_pnl(row, lot):
    sym = row["symbol"]
    pt  = POINT.get(sym, 0.00001)
    cs  = CONTRACT_SIZE.get(sym, 100_000)
    return row["pnl_pts"] * pt * cs * lot

def main():
    if not SIG_CSV.is_file():
        log.error("Signal CSV missing.")
        return

    df = pd.read_csv(SIG_CSV, parse_dates=["time"])
    df = df[df["outcome"].isin(["WIN","LOSS","EXPIRED"])].copy()
    
    # Filter for last 10 days
    max_date = df["time"].max()
    min_date = max_date - timedelta(days=10)
    df = df[df["time"] >= min_date].copy()
    
    df["target"] = (df["outcome"] == "WIN").astype(int)
    log.info(f"Loaded {len(df)} signals for the last 10 days ({min_date.date()} to {max_date.date()})")

    # ML Filtering
    model = joblib.load(MODEL_PATH)
    feats = df[CAT_COLS + NUM_COLS]
    probs = model.predict_proba(feats)[:,1]
    df["win_prob"] = probs
    
    original_len = len(df)
    df = df[df["win_prob"] >= ML_THRESH].copy()
    log.info(f"ML filter kept {len(df)} trades out of {original_len}")
    
    df["lot"] = BASE_LOT
    df["pnl_usd"] = df.apply(lambda r: compute_pnl(r, r["lot"]), axis=1)

    df["date"] = df["time"].dt.date
    df["week"] = df["time"].dt.isocalendar().week
    
    # Daily aggregation
    daily = df.groupby("date").agg(
        trades=("pnl_usd", "count"),
        wins=("target", "sum"),
        pnl=("pnl_usd", "sum")
    ).reset_index()
    daily["win_rate"] = daily["wins"] / daily["trades"] * 100
    daily["cum_cap"] = CAPITAL + daily["pnl"].cumsum()
    daily["peak"] = daily["cum_cap"].cummax()
    daily["dd"] = (daily["cum_cap"] - daily["peak"]) / daily["peak"]
    max_dd = daily["dd"].min() * 100 if len(daily) > 0 else 0.0

    # Weekly aggregation
    weekly = df.groupby("week").agg(
        trades=("pnl_usd", "count"),
        pnl=("pnl_usd", "sum")
    ).reset_index()

    # Strategy breakdown
    strat = df.groupby("strategy").agg(
        trades=("pnl_usd", "count"),
        wins=("target", "sum"),
        pnl=("pnl_usd", "sum")
    ).assign(win_rate=lambda d: d["wins"]/d["trades"]*100).sort_values("pnl", ascending=False)

    # Symbol breakdown
    sym = df.groupby("symbol").agg(
        trades=("pnl_usd", "count"),
        wins=("target", "sum"),
        pnl=("pnl_usd", "sum")
    ).assign(win_rate=lambda d: d["wins"]/d["trades"]*100).sort_values("pnl", ascending=False)

    total_pnl = df["pnl_usd"].sum()
    total_trades = len(df)
    win_rate = (df["target"].sum() / total_trades * 100) if total_trades > 0 else 0
    roi = (total_pnl / CAPITAL) * 100

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# 🏆 Swarm Trading OS — 10-Day Live Simulation Report\n\n")
        f.write(f"**Generated:** {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write(f"**Period:** {min_date.date()} to {max_date.date()}\n")
        f.write(f"**Model:** final_model_sucess.joblib (Threshold: {ML_THRESH})\n\n")

        f.write("## 📊 10-Day Summary\n")
        f.write(f"- **Total Trades Executed:** {total_trades}\n")
        f.write(f"- **Win Rate:** {win_rate:.2f}%\n")
        f.write(f"- **Net P&L:** ${total_pnl:,.2f}\n")
        f.write(f"- **ROI on ${CAPITAL:,.0f}:** {roi:.2f}%\n")
        f.write(f"- **Max Drawdown:** {max_dd:.2f}%\n")
        
        f.write("\n## 📅 Daily Profit & Loss\n")
        f.write("| Date | Trades | Win% | P&L (USD) | Cumulative Capital |\n")
        f.write("|------|--------|------|-----------|--------------------|\n")
        for _, r in daily.iterrows():
            f.write(f"| {r['date']} | {int(r['trades'])} | {r['win_rate']:.1f}% | ${r['pnl']:,.2f} | ${r['cum_cap']:,.2f} |\n")

        f.write("\n## 📆 Weekly Profit & Loss\n")
        f.write("| Week # | Trades | P&L (USD) |\n")
        f.write("|--------|--------|-----------|\n")
        for _, r in weekly.iterrows():
            f.write(f"| Week {int(r['week'])} | {int(r['trades'])} | ${r['pnl']:,.2f} |\n")

        f.write("\n## 💱 Symbol Breakdown\n")
        f.write("| Symbol | Trades | Win% | Total P&L |\n")
        f.write("|--------|--------|------|-----------|\n")
        for s, r in sym.iterrows():
            f.write(f"| {s} | {int(r['trades'])} | {r['win_rate']:.1f}% | ${r['pnl']:,.2f} |\n")

        f.write("\n## 🏆 Strategy Breakdown\n")
        f.write("| Strategy | Trades | Win% | Total P&L |\n")
        f.write("|----------|--------|------|-----------|\n")
        for s, r in strat.iterrows():
            f.write(f"| {s} | {int(r['trades'])} | {r['win_rate']:.1f}% | ${r['pnl']:,.2f} |\n")

    log.info("Report generated successfully.")

if __name__ == '__main__':
    main()
