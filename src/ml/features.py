"""
Centralized Feature Builder for ForexTele ML
=============================================
Provides extract_features() to ensure 100% parity across Backtest, Paper, and Live execution.
No training/serving skew.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any

FEATURE_COLS = [
    "rsi", "atr", "bb_width", "bb_position",
    "ema_slope_9", "ema_slope_21", "ema_cross",
    "mom5", "mom10", "vol_ratio",
    "hour", "dow", "is_london", "is_ny", "is_asian",
    "is_london_ny_overlap", "is_session_open_hour"
]

def extract_df_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes all features over a DataFrame of OHLCV bars.
    Returns DataFrame with FEATURE_COLS appended.
    """
    df = df.copy()

    # RSI
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / (loss + 1e-9)
    df["rsi"] = 100 - 100 / (1 + rs)

    # ATR
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    # Bollinger Bands
    sma20 = df["close"].rolling(20).mean()
    std20 = df["close"].rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    df["bb_width"] = (bb_upper - bb_lower) / (sma20 + 1e-9)
    df["bb_position"] = (df["close"] - bb_lower) / (bb_upper - bb_lower + 1e-9)

    # EMA Slopes & Cross
    ema9  = df["close"].ewm(span=9,  adjust=False).mean()
    ema21 = df["close"].ewm(span=21, adjust=False).mean()
    df["ema_slope_9"]  = (ema9 - ema9.shift(5)) / (ema9.shift(5) + 1e-9) * 100
    df["ema_slope_21"] = (ema21 - ema21.shift(5)) / (ema21.shift(5) + 1e-9) * 100
    df["ema_cross"]    = np.where(ema9 > ema21, 1, -1)

    # Momentum
    df["mom5"]  = (df["close"] - df["close"].shift(5)) / (df["close"].shift(5) + 1e-9) * 100
    df["mom10"] = (df["close"] - df["close"].shift(10)) / (df["close"].shift(10) + 1e-9) * 100

    # Volume Ratio
    vol_col = "volume" if "volume" in df.columns else ("tick_volume" if "tick_volume" in df.columns else None)
    if vol_col:
        vol_avg = df[vol_col].rolling(10).mean()
        df["vol_ratio"] = df[vol_col] / (vol_avg + 1e-9)
    else:
        df["vol_ratio"] = 1.0

    # Session & Time Features
    times = pd.to_datetime(df["time"])
    df["hour"] = times.dt.hour
    df["dow"]  = times.dt.dayofweek
    df["is_london"] = np.where((df["hour"] >= 7) & (df["hour"] <= 16), 1, 0)
    df["is_ny"]     = np.where((df["hour"] >= 13) & (df["hour"] <= 21), 1, 0)
    df["is_asian"]  = np.where((df["hour"] >= 23) | (df["hour"] <= 8), 1, 0)
    df["is_london_ny_overlap"] = np.where((df["hour"] >= 13) & (df["hour"] <= 16), 1, 0)
    df["is_session_open_hour"] = np.where((df["hour"] == 7) | (df["hour"] == 13) | (df["hour"] == 0), 1, 0)

    return df


def extract_features_at_row(df: pd.DataFrame, row_idx: int = -1) -> Dict[str, float]:
    """
    Extracts a feature dictionary for a single candle row.
    Used during live execution when strategy.analyze() emits a signal.
    """
    if "rsi" not in df.columns:
        df = extract_df_features(df)
    row = df.iloc[row_idx]
    return {col: float(row[col]) if not pd.isna(row[col]) else 0.0 for col in FEATURE_COLS}
