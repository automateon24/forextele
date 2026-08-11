"""
ML Signal Filter — Gold Strategy Profitability Predictor
=========================================================
Pipeline:
  1. Fetch wide GOLD bars (10,000 per timeframe) from MT5
  2. Run all 4 positive strategies → collect trades + entry-bar features
  3. Train RandomForest + XGBoost classifiers (WIN=1 / LOSS=0)
  4. Cross-validate and select best model
  5. Re-run "filtered" backtest: only trade when ML confidence >= threshold
  6. Print full comparison report + save model to models/
"""

import sys
import os
import logging
import warnings
import json
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ML_PIPELINE")

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Config ─────────────────────────────────────────────────────────────────
SYMBOL       = "GOLD"
TIMEFRAMES   = ["H1", "M15", "M5"]
STRATEGIES   = ["BOLLINGER_MEAN_REVERSION", "LONDON_SESSION_SCALP", "ASIAN_RANGE_SCALP", "FVG_RETEST"]
CAPITAL      = 1500.0
VOLUME       = 0.02
WIDE_BARS    = 10000      # bars for feature generation (much wider)
ML_THRESHOLD = 0.58       # min predicted WIN probability to take a trade
MODELS_DIR   = ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

# ── MT5 data fetch ─────────────────────────────────────────────────────────
def fetch_bars(symbol: str, timeframe_str: str, bars: int) -> pd.DataFrame:
    import MetaTrader5 as mt5
    TF_MAP = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,  "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    if not mt5.initialize():
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
    rates = mt5.copy_rates_from_pos(symbol, TF_MAP[timeframe_str], 0, bars)
    mt5.shutdown()
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No data returned for {symbol} {timeframe_str}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df[["time", "open", "high", "low", "close", "tick_volume"]].rename(columns={"tick_volume": "volume"})


# ── Technical indicator helpers ────────────────────────────────────────────
def precompute_df_features(df: pd.DataFrame) -> pd.DataFrame:
    """Precompute all technical indicator features on the entire DataFrame vectorized."""
    df = df.copy()

    # RSI(14)
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / (loss + 1e-9)
    df["rsi"] = 100 - 100 / (1 + rs)

    # ATR(14)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift()).abs(), (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    # BB(20, 2)
    sma20 = df["close"].rolling(20).mean()
    std20 = df["close"].rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    df["bb_width"] = (bb_upper - bb_lower) / (sma20 + 1e-9)
    df["bb_position"] = (df["close"] - bb_lower) / (bb_upper - bb_lower + 1e-9)

    # EMAs & slopes
    ema9  = df["close"].ewm(span=9,  adjust=False).mean()
    ema21 = df["close"].ewm(span=21, adjust=False).mean()
    df["ema_slope_9"]  = (ema9 - ema9.shift(5)) / (ema9.shift(5) + 1e-9) * 100
    df["ema_slope_21"] = (ema21 - ema21.shift(5)) / (ema21.shift(5) + 1e-9) * 100
    df["ema_cross"]    = np.where(ema9 > ema21, 1, -1)

    # Momentum
    df["mom5"]  = (df["close"] - df["close"].shift(5)) / (df["close"].shift(5) + 1e-9) * 100
    df["mom10"] = (df["close"] - df["close"].shift(10)) / (df["close"].shift(10) + 1e-9) * 100

    # Volume ratio
    vol_avg = df["volume"].rolling(10).mean()
    df["vol_ratio"] = df["volume"] / (vol_avg + 1e-9)

    # Time features
    times = pd.to_datetime(df["time"])
    df["hour"] = times.dt.hour
    df["dow"]  = times.dt.dayofweek
    df["is_london"] = np.where((df["hour"] >= 7) & (df["hour"] <= 11), 1, 0)
    df["is_ny"]     = np.where((df["hour"] >= 13) & (df["hour"] <= 17), 1, 0)
    df["is_asian"]  = np.where((df["hour"] >= 23) | (df["hour"] <= 6), 1, 0)

    return df


def compute_features(df: pd.DataFrame, entry_idx: int) -> dict:
    """Extract precomputed feature row at entry_idx."""
    FEATURE_COLS = [
        "rsi", "atr", "bb_width", "bb_position",
        "ema_slope_9", "ema_slope_21", "ema_cross",
        "mom5", "mom10", "vol_ratio",
        "hour", "dow", "is_london", "is_ny", "is_asian"
    ]
    if "rsi" not in df.columns:
        df = precompute_df_features(df)
    
    if entry_idx < 20 or entry_idx >= len(df):
        return {}
    
    row = df.iloc[entry_idx]
    return {col: float(row[col]) for col in FEATURE_COLS if not pd.isna(row[col])}



# ── Modified backtest that also captures features ──────────────────────────
def run_feature_backtest(df: pd.DataFrame, strategies, cost_model, capital: float, volume: float) -> pd.DataFrame:
    """Run backtest and capture feature vector at each trade entry."""
    from src.backtest.engine import BacktestEngine

    engine = BacktestEngine(df, strategies, cost_model, capital=capital, volume=volume)
    trades_df = engine.run()
    if trades_df.empty:
        return trades_df

    FEATURE_COLS = [
        "rsi", "atr", "bb_width", "bb_position",
        "ema_slope_9", "ema_slope_21", "ema_cross",
        "mom5", "mom10", "vol_ratio",
        "hour", "dow", "is_london", "is_ny", "is_asian"
    ]
    if "rsi" not in df.columns:
        df = precompute_df_features(df)

    # Fast merge_asof between trades and precomputed features by time
    trades_df = trades_df.sort_values("time")
    df_sorted = df.sort_values("time")
    merged = pd.merge_asof(trades_df, df_sorted[["time"] + FEATURE_COLS], on="time", direction="backward")
    return merged


# ── ML Model Training ──────────────────────────────────────────────────────
def train_model(feature_df: pd.DataFrame, strategy_id: str, timeframe: str):
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.preprocessing import LabelEncoder
    from sklearn.metrics import classification_report, roc_auc_score
    import joblib

    try:
        from xgboost import XGBClassifier
        has_xgb = True
    except ImportError:
        has_xgb = False

    FEATURE_COLS = [
        "rsi", "atr", "bb_width", "bb_position",
        "ema_slope_9", "ema_slope_21", "ema_cross",
        "mom5", "mom10", "vol_ratio",
        "hour", "dow", "is_london", "is_ny", "is_asian"
    ]

    df = feature_df[feature_df["strategy_id"] == strategy_id].copy()
    df = df.dropna(subset=FEATURE_COLS + ["outcome"])
    if len(df) < 30:
        logger.warning(f"  ⚠ Insufficient trades ({len(df)}) for {strategy_id} on {timeframe}")
        return None, None, 0.0

    df["label"] = (df["outcome"] == "WIN").astype(int)
    X = df[FEATURE_COLS].values
    y = df["label"].values

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # ── Random Forest ──────────────────────────────────────────────────────
    rf = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)
    rf_scores = cross_val_score(rf, X, y, cv=cv, scoring="roc_auc")
    rf.fit(X, y)

    # ── XGBoost / GBM ─────────────────────────────────────────────────────
    if has_xgb:
        xgb = XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05,
                             random_state=42, eval_metric="logloss", verbosity=0)
        xgb_scores = cross_val_score(xgb, X, y, cv=cv, scoring="roc_auc")
        xgb.fit(X, y)
        best_model = xgb if xgb_scores.mean() > rf_scores.mean() else rf
        best_score = max(xgb_scores.mean(), rf_scores.mean())
        best_name  = "XGBoost" if xgb_scores.mean() > rf_scores.mean() else "RandomForest"
    else:
        best_model = rf
        best_score = rf_scores.mean()
        best_name  = "RandomForest"

    # ── Feature importance ─────────────────────────────────────────────────
    importances = dict(zip(FEATURE_COLS, best_model.feature_importances_))
    top_feats   = sorted(importances.items(), key=lambda x: -x[1])[:5]

    logger.info(f"  ✅ {strategy_id} ({timeframe}) — Best: {best_name} | ROC-AUC: {best_score:.3f}")
    logger.info(f"     Top features: {top_feats}")

    # ── Save model ─────────────────────────────────────────────────────────
    model_path = MODELS_DIR / f"ml_{strategy_id}_{timeframe}.pkl"
    joblib.dump((best_model, FEATURE_COLS), model_path)
    logger.info(f"     Model saved: {model_path.name}")

    return best_model, FEATURE_COLS, best_score


# ── ML-Filtered Backtest ───────────────────────────────────────────────────
def run_ml_filtered_backtest(df: pd.DataFrame, strategies, cost_model,
                              capital: float, volume: float, models: dict) -> pd.DataFrame:
    """
    Run backtest where each signal is first scored by the ML model.
    Only trades with predicted WIN probability >= ML_THRESHOLD are executed.
    """
    import joblib
    from src.backtest.cost_model import CostModel
    from src.backtest.symbol_specs import get_symbol_spec, calculate_pnl
    from src.backtest.engine import BacktestEngine

    FEATURE_COLS = [
        "rsi", "atr", "bb_width", "bb_position",
        "ema_slope_9", "ema_slope_21", "ema_cross",
        "mom5", "mom10", "vol_ratio",
        "hour", "dow", "is_london", "is_ny", "is_asian"
    ]

    engine = BacktestEngine.__new__(BacktestEngine)
    engine.df          = df
    engine.strategies  = strategies
    engine.cost_model  = cost_model
    engine.capital     = capital
    engine.volume      = volume
    engine.use_tsl     = True
    engine.max_dd_pct  = 0.30
    engine.trades      = []

    max_lookback = max(
        (getattr(s, 'min_bars', getattr(s, 'lookback', 10) + 2) for s in strategies),
        default=50
    )

    running_equity = capital
    peak_equity    = capital
    skipped_ml     = 0
    total_signals  = 0

    for i in range(max_lookback, len(df)):
        window = df.iloc[i - max_lookback: i + 1]
        current_bar_time = window.iloc[-1]['time']

        # 30% portfolio DD cap
        if peak_equity > 0 and (peak_equity - running_equity) / peak_equity >= 0.30:
            continue

        for strategy in strategies:
            signal = strategy.analyze(window)
            if not signal:
                continue

            total_signals += 1
            strat_id = strategy.strategy_id
            model_key = strat_id

            # ── ML Filter ─────────────────────────────────────────────────
            if model_key in models:
                model, _ = models[model_key]
                row = df.iloc[i]
                X_pred = np.array([[row[f] for f in FEATURE_COLS]])
                prob_win = model.predict_proba(X_pred)[0][1]
                if prob_win < ML_THRESHOLD:
                    skipped_ml += 1
                    continue

            trade = engine._simulate_execution(signal, i)
            if trade is None:
                continue

            trade['strategy_id'] = strat_id
            trade['time']        = current_bar_time
            engine.trades.append(trade)

            running_equity += trade['pnl']
            if running_equity > peak_equity:
                peak_equity = running_equity

    logger.info(f"  ML Filter: {skipped_ml}/{total_signals} signals blocked ({100*skipped_ml/max(total_signals,1):.1f}% filtered)")
    return pd.DataFrame(engine.trades)


# ── Metrics helper ────────────────────────────────────────────────────────
def compute_metrics(trades_df: pd.DataFrame, strategy_id: str, capital: float) -> dict:
    df = trades_df[trades_df["strategy_id"] == strategy_id].copy() if "strategy_id" in trades_df.columns else trades_df
    if df.empty:
        return {"strategy_id": strategy_id, "trades": 0, "net_pnl": 0, "return_pct": 0,
                "win_rate": 0, "profit_factor": 0, "max_dd_pct": 0}
    wins    = df[df["outcome"] == "WIN"]["pnl"].sum()
    losses  = df[df["outcome"] == "LOSS"]["pnl"].sum()
    pf      = wins / (-losses + 1e-9) if losses < 0 else float("inf")
    wr      = (df["outcome"] == "WIN").mean() * 100
    net     = df["pnl"].sum()
    equity  = capital + df["pnl"].cumsum()
    peak    = equity.cummax()
    dd      = ((peak - equity) / peak * 100).max()
    return {
        "strategy_id":   strategy_id,
        "trades":        len(df),
        "net_pnl":       round(net, 2),
        "return_pct":    round(net / capital * 100, 2),
        "win_rate":      round(wr, 2),
        "profit_factor": round(pf, 3),
        "max_dd_pct":    round(dd, 2),
    }


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    from src.backtest.cost_model import CostModel

    cost_model = CostModel(spread_points=0.3)

    all_results = []

    for tf in TIMEFRAMES:
        logger.info(f"\n{'='*60}")
        logger.info(f"TIMEFRAME: {tf}  |  {WIDE_BARS} bars  |  $1,500 / 0.02 lot")
        logger.info(f"{'='*60}")

        try:
            df = fetch_bars(SYMBOL, tf, WIDE_BARS)
            df = precompute_df_features(df)
            logger.info(f"  Data: {len(df)} bars | {df['time'].min()} → {df['time'].max()}")
        except Exception as e:
            logger.error(f"  MT5 fetch failed for {tf}: {e}")
            continue

        # ── Load strategies ────────────────────────────────────────────────
        # Map strategy names to their actual class names (handles acronyms like FVG)
        CLASS_NAME_MAP = {
            "BOLLINGER_MEAN_REVERSION": "BollingerMeanReversionStrategy",
            "LONDON_SESSION_SCALP":     "LondonSessionScalpStrategy",
            "ASIAN_RANGE_SCALP":        "AsianRangeScalpStrategy",
            "FVG_RETEST":               "FVGRetestStrategy",
            "NY_OPEN_BREAKOUT":         "NyOpenBreakoutStrategy",
            "LONDON_BREAKOUT_V2":       "LondonBreakoutV2Strategy",
        }
        strategy_instances = []
        for strat_name in STRATEGIES:
            try:
                mod_name = strat_name.lower()
                mod = __import__(f"src.strategy.{mod_name}", fromlist=[mod_name])
                cls_name = CLASS_NAME_MAP.get(strat_name,
                    "".join(w.capitalize() for w in mod_name.split("_")) + "Strategy")
                cls = getattr(mod, cls_name)
                strategy_instances.append(cls(SYMBOL))
            except Exception as e:
                logger.warning(f"  Could not load {strat_name}: {e}")

        if not strategy_instances:
            continue

        # ── Phase 1: Wide backtest with feature capture ────────────────────
        logger.info(f"\n  Phase 1: Wide feature-capture backtest...")
        feature_df = run_feature_backtest(df, strategy_instances, cost_model, CAPITAL, VOLUME)
        logger.info(f"  Captured {len(feature_df)} trades with features")

        # ── Phase 2: Train ML models ───────────────────────────────────────
        logger.info(f"\n  Phase 2: Training ML models...")
        models_this_tf = {}
        model_scores = {}
        for strat_name in STRATEGIES:
            model, feat_cols, score = train_model(feature_df, strat_name, tf)
            if model is not None:
                models_this_tf[strat_name] = (model, feat_cols)
                model_scores[strat_name]   = score

        # ── Phase 3: Baseline backtest (no ML filter) ──────────────────────
        logger.info(f"\n  Phase 3: Baseline backtest (no ML filter)...")
        from src.backtest.engine import BacktestEngine
        engine_base = BacktestEngine(df, strategy_instances, cost_model, capital=CAPITAL, volume=VOLUME)
        base_trades = engine_base.run()

        # ── Phase 4: ML-filtered backtest ─────────────────────────────────
        logger.info(f"\n  Phase 4: ML-filtered backtest (threshold={ML_THRESHOLD})...")
        ml_trades = run_ml_filtered_backtest(df, strategy_instances, cost_model, CAPITAL, VOLUME, models_this_tf)

        # ── Phase 5: Compare results ───────────────────────────────────────
        logger.info(f"\n  {'-'*55}")
        logger.info(f"  RESULTS COMPARISON - {tf}")
        logger.info(f"  {'-'*55}")
        logger.info(f"  {'Strategy':<30} {'Base $':>8} {'Base %':>8} {'ML $':>8} {'ML %':>8} {'ML WR%':>8} {'AUC':>6}")
        logger.info(f"  {'-'*55}")

        for strat_name in STRATEGIES:
            base_m = compute_metrics(base_trades, strat_name, CAPITAL)
            ml_m   = compute_metrics(ml_trades,   strat_name, CAPITAL)
            auc    = model_scores.get(strat_name, 0.0)
            logger.info(
                f"  {strat_name:<30} ${base_m['net_pnl']:>7.0f} {base_m['return_pct']:>7.1f}% "
                f"${ml_m['net_pnl']:>7.0f} {ml_m['return_pct']:>7.1f}% "
                f"{ml_m['win_rate']:>7.1f}% {auc:>5.3f}"
            )
            all_results.append({
                "timeframe": tf,
                "strategy":  strat_name,
                "base_pnl":  base_m["net_pnl"],
                "base_ret":  base_m["return_pct"],
                "base_wr":   base_m["win_rate"],
                "base_dd":   base_m["max_dd_pct"],
                "ml_pnl":    ml_m["net_pnl"],
                "ml_ret":    ml_m["return_pct"],
                "ml_wr":     ml_m["win_rate"],
                "ml_dd":     ml_m["max_dd_pct"],
                "ml_trades": ml_m["trades"],
                "auc":       round(auc, 3),
            })

    # ── Final Summary Report ───────────────────────────────────────────────
    if all_results:
        report_df = pd.DataFrame(all_results)
        report_path = ROOT / "reports" / f"ml_backtest_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        report_path.parent.mkdir(exist_ok=True)
        report_df.to_csv(report_path, index=False)

        print(f"\n  {'-'*70}")
        print("  FINAL ML vs BASELINE SUMMARY REPORT")
        print("="*70)
        print(f"\n  {'TF':<6} {'Strategy':<28} {'Base%':>7} {'ML%':>7} {'ML WR%':>8} {'ML DD%':>8} {'AUC':>6}")
        print(f"  {'-'*70}")
        for _, r in report_df.sort_values("ml_ret", ascending=False).iterrows():
            arrow = "🚀" if r["ml_ret"] > r["base_ret"] else "✅" if r["ml_pnl"] > 0 else "❌"
            print(f"  {r['timeframe']:<6} {r['strategy']:<28} {r['base_ret']:>6.1f}% {r['ml_ret']:>6.1f}% "
                  f"{r['ml_wr']:>7.1f}% {r['ml_dd']:>7.1f}% {r['auc']:>5.3f}  {arrow}")

        best  = report_df[report_df["ml_pnl"] > 0]
        total_base = report_df.groupby("timeframe")["base_pnl"].sum()
        total_ml   = report_df.groupby("timeframe")["ml_pnl"].sum()
        print(f"\n  COMBINED TOTALS PER TIMEFRAME:")
        for tf in TIMEFRAMES:
            b = total_base.get(tf, 0)
            m = total_ml.get(tf, 0)
            improvement = (m - b) / (abs(b) + 1e-9) * 100
            print(f"    {tf}: Baseline ${b:,.0f} → ML-Filtered ${m:,.0f}  ({improvement:+.1f}% change)")

        print(f"\n  Models saved in: {MODELS_DIR}")
        print(f"  CSV report: {report_path}")
        print("="*70)


if __name__ == "__main__":
    main()
