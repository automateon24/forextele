"""
ml_walkforward_trainer.py
=========================
Walk-forward ML training on 1-year backtest signals.
Train: first 270 days | Validate: last 95 days
Tries GradientBoosting, RandomForest, XGBoost (if available).
Saves: ml_1year_best_model.joblib, ml_feature_importance.json
"""
import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, f1_score, roc_auc_score
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BASE_DIR   = Path(r"C:\anlyzeforex\forextele")
SIG_CSV    = BASE_DIR / "backtest_highres_signals.csv"
MODEL_OUT  = BASE_DIR / "second_model_sucess.joblib"
IMP_OUT    = BASE_DIR / "second_model_feature_importance.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CAT_COLS = ["symbol", "strategy", "direction", "session"]
NUM_COLS = ["hour", "weekday", "rsi_val", "adx_val", "atr", "sl_pts", "tp_pts"]


def load_data():
    df = pd.read_csv(SIG_CSV, parse_dates=["time"])
    # Drop EXPIRED — treat only WIN/LOSS
    df = df[df["outcome"].isin(["WIN","LOSS"])].copy()
    df["target"] = (df["outcome"] == "WIN").astype(int)
    # Walk-forward split on date
    df = df.sort_values("time")
    cutoff = df["time"].min() + pd.Timedelta(days=270)
    train = df[df["time"] <  cutoff].copy()
    val   = df[df["time"] >= cutoff].copy()
    log.info("Train rows: %d | Val rows: %d", len(train), len(val))
    return train, val


def build_pipeline(estimator, param_grid):
    preproc = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_COLS),
        ("num", Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc",  StandardScaler()),
        ]), NUM_COLS),
    ])
    pipe = Pipeline([("prep", preproc), ("clf", estimator)])
    return GridSearchCV(pipe, param_grid, scoring="f1_weighted", cv=3, n_jobs=-1, verbose=0)


def main():
    if not SIG_CSV.is_file():
        log.error("Signal CSV not found. Run backtest_1year_all41.py first.")
        return

    train, val = load_data()
    features = CAT_COLS + NUM_COLS
    X_tr = train[features]; y_tr = train["target"]
    X_va = val[features];   y_va = val["target"]

    models = {
        "HistGradientBoosting": (
            HistGradientBoostingClassifier(random_state=42),  # natively handles NaN
            {"clf__max_iter": [200, 400],
             "clf__learning_rate": [0.05, 0.1],
             "clf__max_depth": [3, 4]}
        ),
        "RandomForest": (
            RandomForestClassifier(random_state=42, n_jobs=-1),
            {"clf__n_estimators": [200, 400],
             "clf__max_depth": [None, 10],
             "clf__min_samples_split": [2, 5]}
        ),
    }

    # Add XGBoost if available
    try:
        import xgboost as xgb
        models["XGBoost"] = (
            xgb.XGBClassifier(objective="binary:logistic",
                               eval_metric="logloss",
                               n_jobs=-1, random_state=42,
                               use_label_encoder=False),
            {"clf__n_estimators": [200,400],
             "clf__learning_rate": [0.05,0.1],
             "clf__max_depth": [3,4]}
        )
        log.info("XGBoost available — included in comparison.")
    except ImportError:
        log.info("XGBoost not installed — skipping.")

    best_score = -np.inf
    best_pipe  = None
    best_name  = None
    all_metrics = {}

    for name, (est, pgrid) in models.items():
        log.info("Training %s...", name)
        grid = build_pipeline(est, pgrid)
        grid.fit(X_tr, y_tr)
        best = grid.best_estimator_

        preds = best.predict(X_va)
        probs = best.predict_proba(X_va)[:,1]
        acc   = accuracy_score(y_va, preds)
        f1    = f1_score(y_va, preds, average="weighted")
        roc   = roc_auc_score(y_va, probs)
        log.info("  %s → Acc=%.4f F1=%.4f ROC-AUC=%.4f (best params: %s)",
                 name, acc, f1, roc, grid.best_params_)

        all_metrics[name] = {"accuracy": acc, "f1_weighted": f1, "roc_auc": roc,
                             "best_params": grid.best_params_}
        if f1 > best_score:
            best_score = f1; best_pipe = best; best_name = name

    log.info("Best model: %s (F1=%.4f)", best_name, best_score)
    joblib.dump(best_pipe, MODEL_OUT)
    log.info("Saved → %s", MODEL_OUT)

    # Feature importances (from the classifier inside the pipeline)
    clf = best_pipe.named_steps["clf"]
    prep = best_pipe.named_steps["prep"]
    try:
        cat_names = list(prep.named_transformers_["cat"].get_feature_names_out(CAT_COLS))
        feat_names = cat_names + NUM_COLS
        imps = clf.feature_importances_
        imp_dict = {fn: float(iv) for fn, iv in zip(feat_names, imps)}
        imp_dict["_best_model"] = best_name
        imp_dict["_metrics"] = all_metrics
        with open(IMP_OUT, "w") as f:
            json.dump(imp_dict, f, indent=2)
        log.info("Feature importances saved → %s", IMP_OUT)
        top5 = sorted(imp_dict.items(), key=lambda x: -x[1] if isinstance(x[1], float) else 0)[:5]
        log.info("Top features: %s", top5)
    except Exception as e:
        log.warning("Could not extract feature importances: %s", e)


if __name__ == "__main__":
    main()