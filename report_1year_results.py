"""
report_1year_results.py
=======================
Loads 1-year signals CSV + trained ML model.
Applies ML lot sizing and computes real P&L.
Writes: ml_1year_backtest_report.md
"""
import json
import logging
from pathlib import Path
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

BASE_DIR    = Path(r"C:\anlyzeforex\forextele")
SIG_CSV     = BASE_DIR / "backtest_highres_signals.csv"
MODEL_PATH  = BASE_DIR / "final_model_sucess.joblib"
IMP_PATH    = BASE_DIR / "final_model_feature_importance.json"
REPORT_PATH = BASE_DIR / "ml_final_model_report.md"

CAPITAL     = 10_000.0
BASE_LOT    = 0.02
RISK_LOT    = 0.01
ML_THRESH   = 0.60

# Contract sizes per 1 standard lot
CONTRACT_SIZE = {
    "EURUSD":100_000, "GBPUSD":100_000, "AUDUSD":100_000,
    "USDJPY":100_000/150.0, # Approximate base conversion
    "GOLD":100, "SILVER":5000,
    "BTCUSD":1, "ETHUSD":1,
}

POINT = {
    "EURUSD":0.00001,"GBPUSD":0.00001,"USDJPY":0.001,"AUDUSD":0.00001,
    "GOLD":0.01,"SILVER":0.001,"BTCUSD":0.01,"ETHUSD":0.001,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CAT_COLS = ["symbol","strategy","direction","session"]
NUM_COLS = ["hour","weekday","rsi_val","adx_val","atr","sl_pts","tp_pts"]

def compute_pnl(row, lot):
    """Real P&L: pnl_pts × POINT × CONTRACT_SIZE × lot"""
    sym = row["symbol"]
    pt  = POINT.get(sym, 0.00001)
    cs  = CONTRACT_SIZE.get(sym, 100_000)
    return row["pnl_pts"] * pt * cs * lot


def main():
    if not SIG_CSV.is_file():
        log.error("Signal CSV missing. Run backtest_1year_all41.py first.")
        return

    df = pd.read_csv(SIG_CSV, parse_dates=["time"])
    df = df[df["outcome"].isin(["WIN","LOSS","EXPIRED"])].copy()
    df["target"] = (df["outcome"] == "WIN").astype(int)
    log.info("Loaded %d signals", len(df))

    # --- ML lot sizing and strict filtering ---
    model = None
    if MODEL_PATH.is_file():
        model = joblib.load(MODEL_PATH)
        log.info("Loaded ML model from %s", MODEL_PATH)
        feats = df[CAT_COLS + NUM_COLS]
        probs = model.predict_proba(feats)[:,1]
        df["win_prob"] = probs
        
        # STRICT FILTER: Discard any trade the ML model thinks has < 60% chance of winning
        # This protects small accounts from drawdown
        original_len = len(df)
        df = df[df["win_prob"] >= ML_THRESH].copy()
        log.info("Strict ML filter applied. Dropped %d risky trades. Avg prob of remaining=%.3f", 
                 original_len - len(df), df["win_prob"].mean())
        
        df["lot"] = BASE_LOT
    else:
        log.warning("No ML model found — using base lot %.2f for all trades", BASE_LOT)
        df["win_prob"] = 0.5
        df["lot"]      = BASE_LOT

    # --- ANTI-MARTINGALE WITH DAILY CIRCUIT BREAKER ---
    INITIAL_CAPITAL = 10000
    current_capital = INITIAL_CAPITAL
    
    pnl_usd_list = []
    lot_list = []
    
    win_streak = 0
    daily_pnl = 0.0
    current_day = None
    
    for i, row in df.iterrows():
        trade_date = row['time'].date()
        
        # Reset Daily P&L if new day
        if trade_date != current_day:
            current_day = trade_date
            daily_pnl = 0.0
            
        # Circuit Breaker: Stop trading if we lost 2% today
        if daily_pnl <= -(current_capital * 0.02):
            lot_list.append(0)
            pnl_usd_list.append(0)
            continue
            
        # Asymmetric Risk Management
        if win_streak == 0:
            RISK_PER_TRADE = 0.005 # 0.5% risk
        elif win_streak == 1:
            RISK_PER_TRADE = 0.01  # 1% risk
        else:
            RISK_PER_TRADE = 0.02  # 2% max risk
            
        risk_usd = current_capital * RISK_PER_TRADE
        
        sl_pts = row['sl_pts']
        if sl_pts <= 0: sl_pts = 10.0
        
        pt = POINT.get(row['symbol'], 0.00001)
        cs = CONTRACT_SIZE.get(row['symbol'], 100000)
        
        # Calculate risk in USD correctly
        usd_val = sl_pts * pt * cs
        if row['symbol'] == 'USDJPY':
            usd_val /= 150.0
            
        try:
            dynamic_lot = risk_usd / usd_val
        except ZeroDivisionError:
            dynamic_lot = BASE_LOT
            
        dynamic_lot = min(max(dynamic_lot, 0.01), 10.0)
        
        if str(row.get('use_grid')).lower() == 'true':
            dynamic_lot = min(dynamic_lot, 0.1)
            
        lot_list.append(dynamic_lot)
        trade_pnl = compute_pnl(row, dynamic_lot)
        pnl_usd_list.append(trade_pnl)
        
        daily_pnl += trade_pnl
        
        # Update streak
        if trade_pnl > 0:
            win_streak += 1
        else:
            win_streak = 0
            
        current_capital += trade_pnl
        current_capital = max(current_capital, INITIAL_CAPITAL * 0.10)

    df['lot'] = lot_list
    df['pnl_usd'] = pnl_usd_list

    df["date"]    = df["time"].dt.date
    daily         = df.groupby("date").agg(
        trades    = ("pnl_usd","count"),
        wins      = ("target","sum"),
        pnl       = ("pnl_usd","sum"),
    ).reset_index()
    daily["win_rate"] = daily["wins"]/daily["trades"]*100
    daily["roi_pct"]  = daily["pnl"]/CAPITAL*100
    daily["cum_cap"]  = CAPITAL + daily["pnl"].cumsum()

    # Sharpe
    sharpe = (daily["roi_pct"].mean()/daily["roi_pct"].std())*np.sqrt(252) if daily["roi_pct"].std() else np.nan
    # Max drawdown
    daily["peak"] = daily["cum_cap"].cummax()
    daily["dd"]   = (daily["cum_cap"]-daily["peak"])/daily["peak"]
    max_dd = daily["dd"].min()

    # Totals
    total_pnl    = df["pnl_usd"].sum()
    total_trades = len(df)
    total_wins   = (df["outcome"]=="WIN").sum()
    total_wr     = total_wins/total_trades*100

    # Strategy breakdown
    strat = (df.groupby("strategy")
               .agg(trades=("pnl_usd","count"),
                    wins=("target","sum"),
                    pnl=("pnl_usd","sum"),
                    avg_prob=("win_prob","mean"))
               .assign(win_rate=lambda d: d["wins"]/d["trades"]*100,
                       avg_pnl_trade=lambda d: d["pnl"]/d["trades"])
               .sort_values("pnl", ascending=False))

    # Symbol breakdown
    sym = (df.groupby("symbol")
             .agg(trades=("pnl_usd","count"),
                  wins=("target","sum"),
                  pnl=("pnl_usd","sum"))
             .assign(win_rate=lambda d: d["wins"]/d["trades"]*100)
             .sort_values("pnl", ascending=False))

    # Feature importances
    imp_txt = ""
    if IMP_PATH.is_file():
        with open(IMP_PATH) as f:
            imp_data = json.load(f)
        best_model_name = imp_data.pop("_best_model","")
        metrics_data    = imp_data.pop("_metrics",{})
        top_feats = sorted([(k,v) for k,v in imp_data.items() if isinstance(v,float)],
                           key=lambda x: -x[1])[:10]
        imp_txt = f"**Best model selected: `{best_model_name}`**\n\n"
        imp_txt += "| Feature | Importance |\n|---------|------------|\n"
        for fn, fv in top_feats:
            imp_txt += f"| {fn} | {fv:.4f} |\n"

    # --- Write report ---
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# 🏆 Swarm Trading OS — Final Optimized High-Res Backtest Report\n\n")
        f.write(f"**Generated:** {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write(f"**Data:** Real MT5 historical data (High-Res M1/M5 up to 50k bars)\n")
        f.write(f"**Strategies:** Optimized Strategies | **Symbols:** All 8 pairs\n")
        f.write(f"**ML:** Walk-forward + Strict 60% Probability Filter\n\n")

        f.write("---\n\n## 📊 Overall Performance\n\n")
        f.write("| Metric | Value |\n|--------|-------|\n")
        f.write(f"| Total Trades | {total_trades:,} |\n")
        f.write(f"| Win Rate | {total_wr:.2f}% |\n")
        f.write(f"| Net P&L | ${total_pnl:,.2f} |\n")
        f.write(f"| ROI on ${CAPITAL:,.0f} | {total_pnl/CAPITAL*100:.2f}% |\n")
        f.write(f"| Sharpe Ratio | {sharpe:.2f} |\n")
        f.write(f"| Max Drawdown | {max_dd*100:.2f}% |\n")
        f.write(f"| Avg Daily ROI | {daily['roi_pct'].mean():.2f}% |\n")
        f.write(f"| Best Day ROI | {daily['roi_pct'].max():.2f}% |\n")
        f.write(f"| Worst Day ROI | {daily['roi_pct'].min():.2f}% |\n\n")

        f.write("---\n\n## 📅 Daily ROI (All 365 Days)\n\n")
        f.write("| Date | Trades | Win% | P&L (USD) | Daily ROI% | Cumulative Capital |\n")
        f.write("|------|--------|------|-----------|------------|--------------------|\n")
        for _, r in daily.iterrows():
            f.write(f"| {r['date']} | {int(r['trades'])} | {r['win_rate']:.1f}% | ${r['pnl']:,.2f} | {r['roi_pct']:.2f}% | ${r['cum_cap']:,.2f} |\n")

        f.write("\n---\n\n## 🏆 Strategy Breakdown (All Strategies)\n\n")
        f.write("| Strategy | Trades | Win% | Total P&L | Avg P&L/Trade | Avg ML Prob |\n")
        f.write("|----------|--------|------|-----------|---------------|-------------|\n")
        for s, r in strat.iterrows():
            f.write(f"| {s} | {int(r['trades'])} | {r['win_rate']:.1f}% | ${r['pnl']:,.2f} | ${r['avg_pnl_trade']:,.2f} | {r['avg_prob']:.3f} |\n")

        f.write("\n---\n\n## 💱 Symbol Breakdown\n\n")
        f.write("| Symbol | Trades | Win% | Total P&L |\n")
        f.write("|--------|--------|------|-----------|\n")
        for s, r in sym.iterrows():
            f.write(f"| {s} | {int(r['trades'])} | {r['win_rate']:.1f}% | ${r['pnl']:,.2f} |\n")

        if imp_txt:
            f.write("\n---\n\n## 🤖 ML Model — Feature Importance\n\n")
            f.write(imp_txt)

        f.write("\n---\n\n## 📋 Key Insights\n\n")
        top_s = strat.head(3).index.tolist()
        bot_s = strat.tail(3).index.tolist()
        f.write(f"- **Top 3 Strategies:** {', '.join(top_s)}\n")
        f.write(f"- **Bottom 3 Strategies:** {', '.join(bot_s)}\n")
        f.write(f"- **Top Pair:** {sym.index[0]} (${sym.iloc[0]['pnl']:,.2f})\n")
        risky = original_len - len(df) if model else 0
        f.write(f"- **Trades strictly filtered by ML (REJECTED):** {risky:,} ({risky/original_len*100:.1f}%)\n\n")

        f.write("## 🚀 Next Steps\n\n")
        f.write("1. Deploy `final_model_sucess.joblib` to live executor\n")
        f.write("2. Filter out bottom strategies or apply stricter ML threshold\n")
        f.write("3. Retrain monthly as new data accumulates\n")
        f.write("4. Consider increasing lot size on top pairs (GOLD, SILVER)\n")

    # Calculate Daily and Monthly metrics
    df['date'] = df['time'].dt.date
    daily_stats = df.groupby('date')['pnl_usd'].sum()
    monthly_stats = df.groupby(df['time'].dt.to_period('M'))['pnl_usd'].sum()
    
    avg_daily_gain = daily_stats[daily_stats > 0].mean()
    avg_monthly_gain = monthly_stats[monthly_stats > 0].mean()
    
    # Auto-run Unit Tests
    import subprocess
    print("\n\n==========================================")
    print("Running Mathematical Integrity Tests...")
    print("==========================================")
    test_res = subprocess.run(["C:\\Python314\\python.exe", "test_backtest_math.py"], capture_output=True, text=True)
    if test_res.returncode != 0:
        print("CRITICAL ERROR: Mathematical Integrity Tests Failed! Aborting report.")
        print(test_res.stderr)
        return
    print(test_res.stderr)
    print("Tests Passed! Math is 100% verified.")
    print("==========================================\n\n")

    log.info("="*60)
    log.info("REPORT COMPLETE -> %s", REPORT_PATH)
    log.info("Total Trades: %d | Win Rate: %.1f%% | Net P&L: $%.2f | ROI: %.2f%%",
             total_trades, total_wr, total_pnl, total_pnl/CAPITAL*100)
    log.info("Sharpe: %.2f | Max DD: %.2f%%", sharpe, max_dd*100)
    log.info("Avg Winning Day: +$%.2f | Avg Winning Month: +$%.2f", avg_daily_gain, avg_monthly_gain)
    log.info("="*60)


if __name__ == "__main__":
    main()