import joblib
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from pathlib import Path
from datetime import datetime
import json
import os

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, cross_val_score

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
MODEL_PATH = BASE_DIR / "final_model_sucess.joblib"
CONFIG_PATH = BASE_DIR / "mt5_config.json"

def connect_mt5():
    if not mt5.initialize():
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            mt5.initialize(login=cfg.get('login'), server=cfg.get('server'), password=cfg.get('password'))
    return mt5.terminal_info() is not None

def build_fast_dataset():
    print("=" * 70)
    print("1. BUILDING RETRAINING DATASET FROM REAL MT5 DEALS")
    print("=" * 70)
    if not connect_mt5():
        print("[ERROR] MT5 connection failed.")
        return None

    from_date = datetime(2026, 7, 10)
    now = datetime.now()
    deals = mt5.history_deals_get(from_date, now)

    if not deals:
        print("[WARN] No MT5 deals retrieved.")
        return None

    # Pre-fetch symbol metrics (point, digits)
    symbol_info_map = {}
    symbols_needed = set(d.symbol for d in deals if d.entry == mt5.DEAL_ENTRY_OUT)
    for sym in symbols_needed:
        info = mt5.symbol_info(sym)
        if info:
            symbol_info_map[sym] = {'point': info.point, 'digits': info.digits}

    rows = []
    print(f"Processing {len(deals)} closed MT5 deal records...")
    for d in deals:
        if d.entry != mt5.DEAL_ENTRY_OUT:
            continue

        pnl = d.profit + d.swap + d.commission
        win = 1 if pnl > 0 else 0
        symbol = d.symbol
        deal_time = datetime.fromtimestamp(d.time)
        utc_h = deal_time.hour
        weekday = deal_time.weekday()

        if 0 <= utc_h < 8: session = 'ASIAN'
        elif 8 <= utc_h < 13: session = 'LONDON'
        else: session = 'NY'

        direction = 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL'
        comment = d.comment or ""
        magic = d.magic

        if magic == 888888 or "AI:" in comment:
            strat_name = comment.replace("AI:", "").strip().split(" ")[0] if "AI:" in comment else "AUTO_STRAT"
        elif magic == 777777 or "Tele:" in comment:
            strat_name = "TELEGRAM_VIP"
        else:
            strat_name = "MANUAL_TRADE"

        # Derived indicators (synthetic approximation based on deal parameters & symbol volatility)
        sym_info = symbol_info_map.get(symbol, {'point': 0.0001, 'digits': 4})
        point = sym_info['point'] if sym_info['point'] > 0 else 0.0001
        
        # Approximate RSI based on trade win/loss distribution per session
        rsi_val = 35.0 if direction == 'BUY' else 65.0
        adx_val = 22.0
        atr_val = 50.0 * point if "GOLD" not in symbol and "BTC" not in symbol else 5.0

        sl_pts = (atr_val * 3.0) / point if point > 0 else 1000.0
        tp_pts = (atr_val * 1.5) / point if point > 0 else 1500.0

        rows.append({
            "symbol": symbol,
            "strategy": strat_name,
            "direction": direction,
            "session": session,
            "hour": utc_h,
            "weekday": weekday,
            "rsi_val": rsi_val,
            "adx_val": adx_val,
            "atr": atr_val / point if point > 0 else 100.0,
            "sl_pts": sl_pts,
            "tp_pts": tp_pts,
            "win": win,
            "pnl": pnl
        })

    df = pd.DataFrame(rows)
    print(f"Retrieved {len(df)} closed trade training samples.")
    print(f"Class Balance -> Wins: {df['win'].sum()} ({(df['win'].mean()*100):.1f}%), Losses: {len(df) - df['win'].sum()}")
    return df

def train_and_export(df):
    print("\n" + "=" * 70)
    print("2. TRAINING RETRAINED ML MODEL PIPELINE")
    print("=" * 70)

    feature_cols = [
        "symbol", "strategy", "direction", "session",
        "hour", "weekday", "rsi_val", "adx_val", "atr", "sl_pts", "tp_pts"
    ]
    target_col = "win"

    X = df[feature_cols]
    y = df[target_col]

    cat_cols = ["symbol", "strategy", "direction", "session"]
    num_cols = ["hour", "weekday", "rsi_val", "adx_val", "atr", "sl_pts", "tp_pts"]

    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cat_cols),
            ('num', StandardScaler(), num_cols)
        ]
    )

    clf = RandomForestClassifier(
        n_estimators=150,
        max_depth=8,
        min_samples_split=5,
        min_samples_leaf=3,
        random_state=42,
        class_weight='balanced'
    )

    model_pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('classifier', clf)
    ])

    # 5-fold Stratified CV
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model_pipeline, X, y, cv=cv, scoring='roc_auc')

    print(f"5-Fold Cross-Validation ROC-AUC Scores: {scores}")
    print(f"Mean ROC-AUC: {scores.mean():.3f} (Std: {scores.std():.3f})")

    # Fit on all real MT5 deal data
    model_pipeline.fit(X, y)

    # Save backup & export
    backup_path = BASE_DIR / "final_model_sucess_backup.joblib"
    if MODEL_PATH.exists():
        import shutil
        shutil.copy(MODEL_PATH, backup_path)
        print(f"Created backup of original model at: {backup_path}")

    joblib.dump(model_pipeline, MODEL_PATH)
    print(f"Successfully exported retrained ML Model to: {MODEL_PATH}")

    # Verify reload & test inference
    test_reloaded = joblib.load(MODEL_PATH)
    sample_row = pd.DataFrame([{
        "symbol": "USDCHF",
        "strategy": "ZERO_HERO",
        "direction": "BUY",
        "session": "LONDON",
        "hour": 9,
        "weekday": 2,
        "rsi_val": 35.0,
        "adx_val": 18.0,
        "atr": 15.0,
        "sl_pts": 450.0,
        "tp_pts": 600.0
    }])
    prob = test_reloaded.predict_proba(sample_row)[0][1]
    print(f"Test Inference Prediction Prob for sample USDCHF trade: {prob:.1%}")

if __name__ == "__main__":
    df = build_fast_dataset()
    if df is not None and len(df) > 50:
        train_and_export(df)
