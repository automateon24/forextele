"""
Deep Dive Master Evaluation — ALL 15 STRATEGIES × ALL TIMEFRAMES (H1, M15, M5)
================================================================================
Combines:
  1. All 15 Strategies in the repository
  2. Live-Realistic Execution Engine:
     - Same-bar conflict rule: SL assumed to trigger first if High & Low hit TP & SL.
     - Gap open fill slippage: weekend/news gap open fill.
     - $0.15 entry + $0.15 exit = $0.30 per trade total execution friction.
     - Risk Gate: Min SL distance ($1.00) & Portfolio DD Cap (30%).
  3. Strict Out-Of-Sample (OOS) Walk-Forward ML:
     - 70% Train / 30% Unseen Test Holdout.
     - TimeSeriesSplit CV (0% data leakage).
     - ML Signal Filter (Threshold = 0.58).
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
logger = logging.getLogger("DEEP_DIVE_ML")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SYMBOL       = "GOLD"
TIMEFRAMES   = ["H1", "M15", "M5"]
CAPITAL      = 1500.0
VOLUME       = 0.02
BARS         = 10000
TRAIN_RATIO  = 0.70
ML_THRESHOLD = 0.58

ALL_15_STRATEGIES = [
    ("asian_range_scalp",          "AsianRangeScalpStrategy"),
    ("bollinger_mean_reversion",   "BollingerMeanReversionStrategy"),
    ("ema_trend_pullback",         "EMATrendPullbackStrategy"),
    ("fvg_retest",                 "FVGRetestStrategy"),
    ("london_breakout",            "LondonBreakoutStrategy"),
    ("london_breakout_v2",         "LondonBreakoutV2Strategy"),
    ("london_session_scalp",       "LondonSessionScalpStrategy"),
    ("mean_reversion",             "MeanReversionStrategy"),
    ("ny_open_breakout",           "NYOpenBreakoutStrategy"),
    ("orb_opening_range_breakout", "ORBOpeningRangeBreakoutStrategy"),
    ("rsi_reversal",               "RSIReversalStrategy"),
    ("smc_order_block",            "SMCOrderBlockStrategy"),
    ("supertrend_pullback",        "SupertrendPullbackStrategy"),
    ("trend_momentum",             "TrendMomentumStrategy"),
    ("vwap_mean_reversion",        "VWAPMeanReversionStrategy"),
]

FEATURE_COLS = [
    "rsi", "atr", "bb_width", "bb_position",
    "ema_slope_9", "ema_slope_21", "ema_cross",
    "mom5", "mom10", "vol_ratio",
    "hour", "dow", "is_london", "is_ny", "is_asian"
]


def fetch_bars(symbol: str, timeframe_str: str, bars: int) -> pd.DataFrame:
    import MetaTrader5 as mt5
    TF_MAP = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
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


def precompute_df_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / (loss + 1e-9)
    df["rsi"] = 100 - 100 / (1 + rs)

    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift()).abs(), (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    sma20 = df["close"].rolling(20).mean()
    std20 = df["close"].rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    df["bb_width"] = (bb_upper - bb_lower) / (sma20 + 1e-9)
    df["bb_position"] = (df["close"] - bb_lower) / (bb_upper - bb_lower + 1e-9)

    ema9  = df["close"].ewm(span=9,  adjust=False).mean()
    ema21 = df["close"].ewm(span=21, adjust=False).mean()
    df["ema_slope_9"]  = (ema9 - ema9.shift(5)) / (ema9.shift(5) + 1e-9) * 100
    df["ema_slope_21"] = (ema21 - ema21.shift(5)) / (ema21.shift(5) + 1e-9) * 100
    df["ema_cross"]    = np.where(ema9 > ema21, 1, -1)

    df["mom5"]  = (df["close"] - df["close"].shift(5)) / (df["close"].shift(5) + 1e-9) * 100
    df["mom10"] = (df["close"] - df["close"].shift(10)) / (df["close"].shift(10) + 1e-9) * 100

    vol_avg = df["volume"].rolling(10).mean()
    df["vol_ratio"] = df["volume"] / (vol_avg + 1e-9)

    times = pd.to_datetime(df["time"])
    df["hour"] = times.dt.hour
    df["dow"]  = times.dt.dayofweek
    df["is_london"] = np.where((df["hour"] >= 7) & (df["hour"] <= 11), 1, 0)
    df["is_ny"]     = np.where((df["hour"] >= 13) & (df["hour"] <= 17), 1, 0)
    df["is_asian"]  = np.where((df["hour"] >= 23) | (df["hour"] <= 6), 1, 0)

    return df


def run_feature_backtest(df: pd.DataFrame, strategies, cost_model, capital: float, volume: float) -> pd.DataFrame:
    from src.backtest.engine import BacktestEngine
    engine = BacktestEngine(df, strategies, cost_model, capital=capital, volume=volume)
    trades_df = engine.run()
    if trades_df.empty:
        return trades_df

    if "rsi" not in df.columns:
        df = precompute_df_features(df)

    trades_df = trades_df.sort_values("time")
    df_sorted = df.sort_values("time")
    merged = pd.merge_asof(trades_df, df_sorted[["time"] + FEATURE_COLS], on="time", direction="backward")
    return merged


def train_model_strict_oos(train_feature_df: pd.DataFrame, strategy_id: str, timeframe: str):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import TimeSeriesSplit, cross_val_score

    try:
        from xgboost import XGBClassifier
        has_xgb = True
    except ImportError:
        has_xgb = False

    df = train_feature_df[train_feature_df["strategy_id"] == strategy_id].copy()
    df = df.dropna(subset=FEATURE_COLS + ["outcome"])

    if len(df) < 15:
        return None, 0.0

    df["label"] = (df["outcome"] == "WIN").astype(int)
    X = df[FEATURE_COLS].values
    y = df["label"].values

    if len(np.unique(y)) < 2:
        return None, 0.0

    tscv = TimeSeriesSplit(n_splits=min(4, max(2, len(df)//10)))

    rf = RandomForestClassifier(n_estimators=150, max_depth=5, random_state=42, n_jobs=-1)
    rf_scores = cross_val_score(rf, X, y, cv=tscv, scoring="roc_auc")
    rf.fit(X, y)

    if has_xgb:
        xgb = XGBClassifier(n_estimators=150, max_depth=3, learning_rate=0.03, random_state=42, eval_metric="logloss", verbosity=0)
        xgb_scores = cross_val_score(xgb, X, y, cv=tscv, scoring="roc_auc")
        xgb.fit(X, y)

        rf_auc  = np.nanmean(rf_scores)  if len(rf_scores)  > 0 else 0.5
        xgb_auc = np.nanmean(xgb_scores) if len(xgb_scores) > 0 else 0.5

        best_model = xgb if xgb_auc > rf_auc else rf
        best_score = max(xgb_auc, rf_auc)
    else:
        best_model = rf
        best_score = np.nanmean(rf_scores) if len(rf_scores) > 0 else 0.5

    return best_model, float(best_score)


def run_oos_backtest(test_df: pd.DataFrame, strategies, cost_model, capital: float, volume: float, models: dict, use_ml: bool = False) -> pd.DataFrame:
    from src.backtest.engine import BacktestEngine
    engine = BacktestEngine.__new__(BacktestEngine)
    engine.df           = test_df
    engine.strategies   = strategies
    engine.cost_model   = cost_model
    engine.capital      = capital
    engine.volume       = volume
    engine.use_tsl      = True
    engine.max_dd_pct   = 0.30
    engine.slippage_usd = 0.15
    engine.trades       = []

    max_lookback = max(
        (getattr(s, 'min_bars', getattr(s, 'lookback', 10) + 2) for s in strategies),
        default=50
    )

    running_equity = capital
    peak_equity    = capital

    for i in range(max_lookback, len(test_df)):
        window = test_df.iloc[i - max_lookback: i + 1]
        current_bar_time = window.iloc[-1]['time']

        if peak_equity > 0 and (peak_equity - running_equity) / peak_equity >= 0.30:
            continue

        for strategy in strategies:
            signal = strategy.analyze(window)
            if not signal:
                continue

            sl_dist = abs(signal.suggested_entry_price - signal.suggested_sl_price)
            if sl_dist < 1.00:
                continue

            strat_id = strategy.strategy_id

            if use_ml and strat_id in models and models[strat_id] is not None:
                model = models[strat_id]
                row = test_df.iloc[i]
                X_pred = np.array([[row[f] for f in FEATURE_COLS]])
                prob_win = model.predict_proba(X_pred)[0][1]
                if prob_win < ML_THRESHOLD:
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

    return pd.DataFrame(engine.trades)


def compute_metrics(trades_df: pd.DataFrame, strategy_id: str, capital: float) -> dict:
    df = trades_df[trades_df["strategy_id"] == strategy_id].copy() if ("strategy_id" in trades_df.columns and not trades_df.empty) else trades_df
    if df.empty:
        return {"strategy_id": strategy_id, "trades": 0, "net_pnl": 0.0, "return_pct": 0.0,
                "win_rate": 0.0, "profit_factor": 0.0, "max_dd_pct": 0.0}
    wins    = df[df["outcome"] == "WIN"]["pnl"].sum()
    losses  = df[df["outcome"] == "LOSS"]["pnl"].sum()
    pf      = wins / (-losses + 1e-9) if losses < 0 else (99.0 if wins > 0 else 0.0)
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


def main():
    from src.backtest.cost_model import CostModel

    cost_model = CostModel(spread_points=0.3)
    all_results = []

    print("\n" + "="*85)
    print("  DEEP DIVE EVALUATION — ALL 15 STRATEGIES × ALL TIMEFRAMES (H1, M15, M5)")
    print("  Execution Realism: Pessimistic Same-Bar SL + Gap Open Slippage + $0.30/trade friction")
    print("  Validation: Strict 70% Historical Train / 30% Unseen OOS Test Holdout")
    print("="*85)

    for tf in TIMEFRAMES:
        logger.info(f"\n==================== TIMEFRAME: {tf} ====================")
        try:
            df = fetch_bars(SYMBOL, tf, BARS)
            df = precompute_df_features(df)
        except Exception as e:
            logger.error(f"Fetch failed for {tf}: {e}")
            continue

        split_idx = int(len(df) * TRAIN_RATIO)
        train_df  = df.iloc[:split_idx].copy().reset_index(drop=True)
        test_df   = df.iloc[split_idx:].copy().reset_index(drop=True)

        logger.info(f"  Train: {train_df['time'].iloc[0]} -> {train_df['time'].iloc[-1]} ({len(train_df)} bars)")
        logger.info(f"  Test:  {test_df['time'].iloc[0]} -> {test_df['time'].iloc[-1]} ({len(test_df)} bars - UNSEEN HOLDOUT)")

        # Load all 15 strategy instances
        strategy_instances = []
        loaded_names = []
        for mod_file, cls_name in ALL_15_STRATEGIES:
            try:
                mod = __import__(f"src.strategy.{mod_file}", fromlist=[mod_file])
                cls = getattr(mod, cls_name)
                strategy_instances.append(cls(SYMBOL))
                loaded_names.append(getattr(cls(SYMBOL), 'strategy_id', cls_name))
            except Exception as e:
                logger.warning(f"Could not load {cls_name}: {e}")

        logger.info(f"  Loaded {len(strategy_instances)} strategies.")

        # Step 1: Feature capture backtest on 70% Train
        train_trades = run_feature_backtest(train_df, strategy_instances, cost_model, CAPITAL, VOLUME)
        logger.info(f"  Simulated {len(train_trades)} trades on Train set.")

        # Step 2: Train ML models on 70% Train
        models = {}
        model_scores = {}
        for strat in strategy_instances:
            s_id = strat.strategy_id
            model, auc = train_model_strict_oos(train_trades, s_id, tf)
            models[s_id]       = model
            model_scores[s_id] = auc

        # Step 3: Run Baseline Backtest on 30% UNSEEN Holdout
        base_test_trades = run_oos_backtest(test_df, strategy_instances, cost_model, CAPITAL, VOLUME, models, use_ml=False)

        # Step 4: Run ML-Filtered Backtest on 30% UNSEEN Holdout
        ml_test_trades   = run_oos_backtest(test_df, strategy_instances, cost_model, CAPITAL, VOLUME, models, use_ml=True)

        # Step 5: Print table for this timeframe
        print(f"\n  --- {tf} OUT-OF-SAMPLE HOLDOUT RESULTS ({test_df['time'].iloc[0].strftime('%Y-%m-%d')} to {test_df['time'].iloc[-1].strftime('%Y-%m-%d')}) ---")
        print(f"  {'-'*85}")
        print(f"  {'Strategy':<32} {'Base Ret%':>10} {'ML OOS Ret%':>12} {'ML OOS WR%':>12} {'ML OOS PF':>10} {'ML OOS DD%':>10}")
        print(f"  {'-'*85}")

        for strat in strategy_instances:
            s_id = strat.strategy_id
            b_m  = compute_metrics(base_test_trades, s_id, CAPITAL)
            ml_m = compute_metrics(ml_test_trades,   s_id, CAPITAL)
            auc  = model_scores.get(s_id, 0.0)

            print(f"  {s_id:<32} {b_m['return_pct']:>9.1f}% {ml_m['return_pct']:>11.1f}% {ml_m['win_rate']:>11.1f}% {ml_m['profit_factor']:>9.2f} {ml_m['max_dd_pct']:>9.1f}%")

            all_results.append({
                "timeframe":      tf,
                "strategy":       s_id,
                "base_oos_ret":   b_m["return_pct"],
                "ml_oos_ret":     ml_m["return_pct"],
                "ml_oos_wr":      ml_m["win_rate"],
                "ml_oos_pf":      ml_m["profit_factor"],
                "ml_oos_dd":      ml_m["max_dd_pct"],
                "ml_oos_trades":  ml_m["trades"],
                "auc":            round(auc, 3),
            })

    # Summary Report
    report_df = pd.DataFrame(all_results)
    report_path = ROOT / "reports" / f"deep_dive_all15_strategies_oos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    report_df.to_csv(report_path, index=False)

    print("\n" + "="*85)
    print("  GRAND SUMMARY — TOP SURVIVING STRATEGIES ACROSS ALL 15 (UNSEEN HOLDOUT)")
    print("="*85)
    positive_df = report_df[report_df["ml_oos_ret"] > 0].sort_values("ml_oos_ret", ascending=False)
    print(f"  {'TF':<5} {'Strategy':<32} {'Base OOS%':>10} {'ML OOS%':>10} {'ML WR%':>9} {'ML PF':>8} {'ML DD%':>8}")
    print(f"  {'-'*85}")
    for _, r in positive_df.iterrows():
        print(f"  {r['timeframe']:<5} {r['strategy']:<32} {r['base_oos_ret']:>9.1f}% {r['ml_oos_ret']:>9.1f}% {r['ml_oos_wr']:>8.1f}% {r['ml_oos_pf']:>7.2f} {r['ml_oos_dd']:>7.1f}%")

    print("="*85)
    print(f"  Report saved to: {report_path}\n")


if __name__ == "__main__":
    main()
