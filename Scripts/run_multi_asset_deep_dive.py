"""
Multi-Asset Master Deep Dive — GOLD + EURUSD + GBPUSD
=====================================================
Evaluates core strategies across GOLD, EURUSD, GBPUSD on H1, M15, M5
under 100% Live-Realistic Execution (pessimistic same-bar SL, gap open slippage,
symbol-specific spreads & slippage, strict 70/30 OOS walk-forward).
"""

import sys
import os
import logging
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MULTI_ASSET_ML")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SYMBOLS       = ["GOLD", "EURUSD", "GBPUSD"]
TIMEFRAMES    = ["H1", "M15", "M5"]
CAPITAL       = 1500.0
EXPANDED_BARS = 3500      # 3.5k bars per asset/TF (~6 mo H1, 1.5 mo M15, 0.5 mo M5)
TRAIN_RATIO   = 0.70      # 70% Train, 30% Unseen OOS Holdout
ML_THRESHOLD  = 0.58

CORE_STRATEGIES = [
    ("asian_range_scalp",          "AsianRangeScalpStrategy"),
    ("bollinger_mean_reversion",   "BollingerMeanReversionStrategy"),
    ("fvg_retest",                 "FVGRetestStrategy"),
    ("london_breakout_v2",         "LondonBreakoutV2Strategy"),
    ("london_session_scalp",       "LondonSessionScalpStrategy"),
    ("orb_opening_range_breakout", "ORBOpeningRangeBreakoutStrategy"),
    ("trend_momentum",             "TrendMomentumStrategy"),
]

FEATURE_COLS = [
    "rsi", "atr", "bb_width", "bb_position",
    "ema_slope_9", "ema_slope_21", "ema_cross",
    "mom5", "mom10", "vol_ratio",
    "hour", "dow", "is_london", "is_ny", "is_asian"
]

# Symbol Specific Specs for Cost & Risk Realism
SYMBOL_PARAMS = {
    "GOLD":   {"spread_points": 0.30, "slippage_usd": 0.15, "min_sl": 1.00},
    "EURUSD": {"spread_points": 0.80, "slippage_usd": 0.00005, "min_sl": 0.00050},
    "GBPUSD": {"spread_points": 1.20, "slippage_usd": 0.00008, "min_sl": 0.00080},
}


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


def run_feature_backtest(df: pd.DataFrame, strategies, cost_model, capital: float, volume: float, symbol: str) -> pd.DataFrame:
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


def train_model_strict_oos(train_feature_df: pd.DataFrame, strategy_id: str):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import TimeSeriesSplit, cross_val_score

    try:
        from xgboost import XGBClassifier
        has_xgb = True
    except ImportError:
        has_xgb = False

    df = train_feature_df[train_feature_df["strategy_id"] == strategy_id].copy()
    df = df.dropna(subset=FEATURE_COLS + ["outcome"])

    if len(df) < 10:
        return None, 0.0

    df["label"] = (df["outcome"] == "WIN").astype(int)
    X = df[FEATURE_COLS].values
    y = df["label"].values

    if len(np.unique(y)) < 2:
        return None, 0.0

    tscv = TimeSeriesSplit(n_splits=min(3, max(2, len(df)//8)))

    rf = RandomForestClassifier(n_estimators=100, max_depth=4, random_state=42, n_jobs=-1)
    try:
        rf_scores = cross_val_score(rf, X, y, cv=tscv, scoring="roc_auc")
        rf_auc = float(np.nanmean(rf_scores)) if len(rf_scores) > 0 else 0.5
    except Exception:
        rf_auc = 0.5
    rf.fit(X, y)

    if has_xgb:
        xgb = XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.03, random_state=42, eval_metric="logloss", verbosity=0)
        try:
            xgb_scores = cross_val_score(xgb, X, y, cv=tscv, scoring="roc_auc")
            xgb_auc = float(np.nanmean(xgb_scores)) if len(xgb_scores) > 0 else 0.5
        except Exception:
            xgb_auc = 0.5
        xgb.fit(X, y)

        best_model = xgb if xgb_auc > rf_auc else rf
        best_score = max(xgb_auc, rf_auc)
    else:
        best_model = rf
        best_score = rf_auc

    return best_model, float(best_score)


def run_oos_backtest(test_df: pd.DataFrame, strategies, cost_model, capital: float, volume: float, models: dict, symbol: str, use_ml: bool = False) -> pd.DataFrame:
    from src.backtest.engine import BacktestEngine
    params = SYMBOL_PARAMS.get(symbol, SYMBOL_PARAMS["GOLD"])

    engine = BacktestEngine.__new__(BacktestEngine)
    engine.df           = test_df
    engine.strategies   = strategies
    engine.cost_model   = cost_model
    engine.capital      = capital
    engine.volume       = volume
    engine.use_tsl      = True
    engine.max_dd_pct   = 0.30
    engine.slippage_usd = params["slippage_usd"]
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
            if sl_dist < params["min_sl"]:
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

    all_multi_results = []

    print("\n" + "="*90)
    print("  MULTI-ASSET MASTER DEEP DIVE — GOLD + EURUSD + GBPUSD")
    print("  Dataset: 3,500 Bars per Asset/TF (~6 mo H1, 1.5 mo M15, 0.5 mo M5)")
    print("  Execution Realism: Pessimistic Same-Bar SL + Gap Open Fills + Asset-Specific Slippage")
    print("  Validation: Strict 70% Historical Train / 30% Unseen OOS Test Holdout")
    print("="*90)

    for symbol in SYMBOLS:
        params = SYMBOL_PARAMS[symbol]
        cost_model = CostModel(spread_points=params["spread_points"])

        for tf in TIMEFRAMES:
            logger.info(f"Processing {symbol} {tf}...")
            try:
                df = fetch_bars(symbol, tf, EXPANDED_BARS)
                df = precompute_df_features(df)
            except Exception as e:
                logger.error(f"Fetch failed for {symbol} {tf}: {e}")
                continue

            split_idx = int(len(df) * TRAIN_RATIO)
            train_df  = df.iloc[:split_idx].copy().reset_index(drop=True)
            test_df   = df.iloc[split_idx:].copy().reset_index(drop=True)

            strategy_instances = []
            for mod_file, cls_name in CORE_STRATEGIES:
                try:
                    mod = __import__(f"src.strategy.{mod_file}", fromlist=[mod_file])
                    cls = getattr(mod, cls_name)
                    strategy_instances.append(cls(symbol))
                except Exception as e:
                    pass

            train_trades = run_feature_backtest(train_df, strategy_instances, cost_model, CAPITAL, volume=0.02, symbol=symbol)
            active_strat_ids = train_trades["strategy_id"].unique() if not train_trades.empty else []
            active_strategies = [s for s in strategy_instances if s.strategy_id in active_strat_ids]

            models = {}
            for strat in active_strategies:
                s_id = strat.strategy_id
                model, auc = train_model_strict_oos(train_trades, s_id)
                models[s_id] = model

            base_test_trades = run_oos_backtest(test_df, active_strategies, cost_model, CAPITAL, volume=0.02, models=models, symbol=symbol, use_ml=False)
            ml_test_trades   = run_oos_backtest(test_df, active_strategies, cost_model, CAPITAL, volume=0.02, models=models, symbol=symbol, use_ml=True)

            for strat in active_strategies:
                s_id = strat.strategy_id
                b_m  = compute_metrics(base_test_trades, s_id, CAPITAL)
                ml_m = compute_metrics(ml_test_trades,   s_id, CAPITAL)

                all_multi_results.append({
                    "symbol":         symbol,
                    "timeframe":      tf,
                    "strategy":       s_id,
                    "base_oos_ret":   b_m["return_pct"],
                    "ml_oos_ret":     ml_m["return_pct"],
                    "ml_oos_wr":      ml_m["win_rate"],
                    "ml_oos_pf":      ml_m["profit_factor"],
                    "ml_oos_dd":      ml_m["max_dd_pct"],
                    "ml_oos_trades":  ml_m["trades"],
                })

    report_df = pd.DataFrame(all_multi_results)
    report_path = ROOT / "reports" / f"multi_asset_deep_dive_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    report_df.to_csv(report_path, index=False)

    print("\n" + "="*90)
    print("  MULTI-ASSET GRAND SUMMARY — ALL SURVIVING ML STRATEGIES (UNSEEN HOLDOUT)")
    print("="*90)
    positive_df = report_df[report_df["ml_oos_ret"] > 0].sort_values("ml_oos_ret", ascending=False)
    print(f"  {'Symbol':<8} {'TF':<5} {'Strategy':<30} {'Base OOS%':>10} {'ML OOS%':>10} {'ML WR%':>9} {'ML PF':>8} {'ML DD%':>8}")
    print(f"  {'-'*90}")
    for _, r in positive_df.iterrows():
        print(f"  {r['symbol']:<8} {r['timeframe']:<5} {r['strategy']:<30} {r['base_oos_ret']:>9.1f}% {r['ml_oos_ret']:>9.1f}% {r['ml_oos_wr']:>8.1f}% {r['ml_oos_pf']:>7.2f} {r['ml_oos_dd']:>7.1f}%")

    print("="*90)
    print(f"  Report saved to: {report_path}\n")


if __name__ == "__main__":
    main()
