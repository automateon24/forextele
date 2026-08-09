"""
ml_backtest_report.py
=====================
Back-test Swarm-OS signals with ML-augmented lot sizing.
Uses backtest_1week_results.csv which already contains
the actual trade outcomes.

If ml_best_classifier.joblib is present → lot is adjusted per ML probability.
If the model is not yet trained  → raw simulation at base lot (no ML).

Output: ml_backtest_report.md
"""

import logging
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

BASE_DIR    = Path(r"C:\anlyzeforex\forextele")
BT_CSV      = BASE_DIR / "backtest_1week_results.csv"
MODEL_PATH  = BASE_DIR / "ml_best_classifier.joblib"
REPORT_PATH = BASE_DIR / "ml_backtest_report.md"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Session helper
# --------------------------------------------------------------------------- #
def session_flag(hour: int) -> str:
    if hour < 4:   return "ASIAN"
    if hour < 8:   return "LONDON"
    if hour < 12:  return "NY"
    if hour < 16:  return "US"
    return "LONDON"

# --------------------------------------------------------------------------- #
# Load model (optional)
# --------------------------------------------------------------------------- #
def try_load_model():
    if not MODEL_PATH.is_file():
        log.info("No trained model found – running in RAW mode (no ML sizing).")
        return None
    try:
        import joblib
        model = joblib.load(MODEL_PATH)
        log.info("Loaded ML model from %s", MODEL_PATH)
        return model
    except Exception as exc:
        log.warning("Could not load model (%s) – RAW mode.", exc)
        return None

# --------------------------------------------------------------------------- #
# Win probability helper
# --------------------------------------------------------------------------- #
def win_probability(model, row: pd.Series) -> float:
    hour    = pd.to_datetime(row["time"]).hour
    weekday = pd.to_datetime(row["time"]).weekday()
    feature = {
        "symbol":      row["symbol"],
        "strategy":    row["strategy"],
        "direction":   row["direction"],
        "open":        row["entry"],
        "high":        row["entry"] * 1.001,
        "low":         row["entry"] * 0.999,
        "close":       row["entry"],
        "tick_volume": 1.0,
        "entry":       row["entry"],
        "sl_pts":      row["sl_pts"],
        "tp_pts":      row["tp_pts"],
        "atr":         row["atr"],
        "hour":        hour,
        "weekday":     weekday,
        "session":     session_flag(hour),
    }
    df = pd.DataFrame([feature])
    return float(model.predict_proba(df)[0, 1])

# --------------------------------------------------------------------------- #
# Simulate one trade
# --------------------------------------------------------------------------- #
BASE_LOT   = 0.02        # baseline lot per signal
CAPITAL    = 10_000.0    # USD starting capital
ML_THRESH  = 0.55        # probability threshold for lot reduction

def simulate_trade(row: pd.Series, model) -> dict:
    lot     = BASE_LOT
    prob    = 0.5
    ml_used = False

    if model is not None:
        try:
            prob    = win_probability(model, row)
            ml_used = True
            if prob < ML_THRESH:
                lot = max(lot * 0.5, 0.01)
        except Exception as exc:
            log.debug("ML inference failed for row: %s", exc)

    # Use the actual pnl_usd from the CSV rescaled to our lot size
    # Original CSV was generated at the DNA-optimized lot; we rescale proportionally.
    original_pnl = float(row["pnl_usd"])
    # Assume the CSV lot is BASE_LOT – if you know the original lot, set it here.
    scaled_pnl   = original_pnl * (lot / BASE_LOT)

    return {
        "timestamp":   row["time"],
        "symbol":      row["symbol"],
        "strategy":    row["strategy"],
        "direction":   row["direction"],
        "outcome":     row["outcome"],
        "pnl":         scaled_pnl,
        "lot_used":    lot,
        "win_prob":    prob,
        "ml_used":     ml_used,
    }

# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run_backtest():
    if not BT_CSV.is_file():
        log.error("CSV not found: %s", BT_CSV)
        return

    df = pd.read_csv(BT_CSV, parse_dates=["time"])
    log.info("Loaded %d signals from CSV.", len(df))

    model = try_load_model()
    mode  = "ML-Augmented" if model else "RAW (no ML model)"
    log.info("Running in %s mode.", mode)

    results = [simulate_trade(r, model) for _, r in df.iterrows()]
    res = pd.DataFrame(results)

    # ----- Aggregate --------------------------------------------------------
    total_trades  = len(res)
    win_rate      = (res["outcome"] == "WIN").mean()
    total_pnl     = res["pnl"].sum()
    avg_lot       = res["lot_used"].mean()
    avg_winprob   = res["win_prob"].mean()
    roi_pct       = total_pnl / CAPITAL * 100

    res["date"]   = pd.to_datetime(res["timestamp"]).dt.date
    daily         = res.groupby("date")["pnl"].sum().reset_index()
    daily["cum"]  = CAPITAL + daily["pnl"].cumsum()
    daily["roi%"] = daily["pnl"] / CAPITAL * 100

    if daily["roi%"].std() > 0:
        sharpe = (daily["roi%"].mean() / daily["roi%"].std()) * np.sqrt(252)
    else:
        sharpe = np.nan

    daily["peak"] = daily["cum"].cummax()
    daily["dd"]   = (daily["cum"] - daily["peak"]) / daily["peak"]
    max_dd        = daily["dd"].min()

    # Strategy breakdown
    strat_summary = (
        res.groupby("strategy")
           .agg(trades=("pnl","count"),
                wins=("outcome", lambda x: (x=="WIN").sum()),
                pnl=("pnl","sum"))
           .assign(win_rate=lambda d: d["wins"]/d["trades"]*100,
                   avg_pnl=lambda d: d["pnl"]/d["trades"])
           .sort_values("pnl", ascending=False)
    )

    # Symbol breakdown
    sym_summary = (
        res.groupby("symbol")
           .agg(trades=("pnl","count"),
                wins=("outcome", lambda x: (x=="WIN").sum()),
                pnl=("pnl","sum"))
           .assign(win_rate=lambda d: d["wins"]/d["trades"]*100)
           .sort_values("pnl", ascending=False)
    )

    # ----- Write report -----------------------------------------------------
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# ML-Augmented Back-test Report\n\n")
        f.write(f"**Mode:** {mode}\n\n")
        f.write(f"**Run date:** {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
        f.write(f"**Data source:** `backtest_1week_results.csv`\n\n")

        f.write("---\n\n## 📊 Overall Summary\n\n")
        f.write(f"| Metric | Value |\n|--------|-------|\n")
        f.write(f"| Total trades | {total_trades:,} |\n")
        f.write(f"| Overall win-rate | {win_rate*100:.2f}% |\n")
        f.write(f"| Net P&L | ${total_pnl:,.2f} |\n")
        f.write(f"| Return on ${CAPITAL:,.0f} capital | {roi_pct:.2f}% |\n")
        f.write(f"| Average lot used | {avg_lot:.4f} |\n")
        f.write(f"| Avg ML win-probability | {avg_winprob:.3f} |\n")
        f.write(f"| Sharpe ratio (annualised) | {sharpe:.2f} |\n")
        f.write(f"| Max draw-down | {max_dd*100:.2f}% |\n\n")

        f.write("---\n\n## 📅 Daily ROI\n\n")
        f.write("| Date | P&L (USD) | Daily ROI % | Cumulative Capital |\n")
        f.write("|------|-----------|-------------|--------------------|\n")
        for _, r in daily.iterrows():
            f.write(f"| {r['date']} | ${r['pnl']:,.2f} | {r['roi%']:.2f}% | ${r['cum']:,.2f} |\n")

        f.write("\n---\n\n## 🏆 Strategy Breakdown (Top 20)\n\n")
        f.write("| Strategy | Trades | Win% | Total P&L | Avg P&L/trade |\n")
        f.write("|----------|--------|------|-----------|---------------|\n")
        for strat, r in strat_summary.head(20).iterrows():
            f.write(f"| {strat} | {r['trades']} | {r['win_rate']:.1f}% | ${r['pnl']:,.2f} | ${r['avg_pnl']:,.2f} |\n")

        f.write("\n---\n\n## 💱 Symbol Breakdown\n\n")
        f.write("| Symbol | Trades | Win% | Total P&L |\n")
        f.write("|--------|--------|------|-----------|\n")
        for sym, r in sym_summary.iterrows():
            f.write(f"| {sym} | {r['trades']} | {r['win_rate']:.1f}% | ${r['pnl']:,.2f} |\n")

        f.write("\n---\n\n## 🤖 ML Model Impact\n\n")
        if model:
            risky = (res["win_prob"] < ML_THRESH).sum()
            f.write(f"- **{risky} signals** ({risky/total_trades*100:.1f}%) flagged as risky (prob < {ML_THRESH})\n")
            f.write(f"- Those signals had their lot reduced to 50% of base lot\n")
            f.write(f"- Remaining **{total_trades-risky} signals** traded at full lot\n\n")
        else:
            f.write("- No ML model found. All trades used base lot of 0.02.\n")
            f.write("- Run `ml_experiment_pipeline.py` to train a model and improve sizing.\n\n")

        f.write("---\n\n## 🚀 Next Steps\n\n")
        f.write("1. **Train the ML model** (`python ml_experiment_pipeline.py`) for smarter sizing\n")
        f.write("2. **Fetch 1-year data** (`python fetch_one_year_data.py`) to improve training\n")
        f.write("3. **Re-run this script** after training to compare ML vs RAW performance\n")
        f.write("4. **Adjust threshold** (currently 0.55) if you want more/less conservative sizing\n")

    log.info("Report written to %s", REPORT_PATH)
    print(f"\n{'='*60}")
    print(f"  BACKTEST COMPLETE")
    print(f"{'='*60}")
    print(f"  Mode:         {mode}")
    print(f"  Total trades: {total_trades:,}")
    print(f"  Win rate:     {win_rate*100:.2f}%")
    print(f"  Net P&L:      ${total_pnl:,.2f}")
    print(f"  ROI:          {roi_pct:.2f}%")
    print(f"  Sharpe:       {sharpe:.2f}")
    print(f"  Max DD:       {max_dd*100:.2f}%")
    print(f"  Report:       {REPORT_PATH}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    run_backtest()
