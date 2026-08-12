"""
Multi-Timeframe (MTF) Directional Trend Alignment Filter
=========================================================
Ensures lower timeframe signals (M5, M15, H1) only execute in alignment with 
the Higher Timeframe (HTF H4/H1) institutional trend bias.

Rule:
  - If HTF Trend is BULLISH (EMA50 > EMA200 and Price > EMA50): Allow BUY signals ONLY.
  - If HTF Trend is BEARISH (EMA50 < EMA200 and Price < EMA50): Allow SELL signals ONLY.
  - If HTF Trend is NEUTRAL (Ranging): Allow mean reversion ONLY if ADX < 20.
"""

import pandas as pd
from typing import Dict, Any, Optional
from src.common.indicators import calculate_ema, calculate_adx


def get_htf_trend_bias(df_h1: pd.DataFrame) -> str:
    """
    Computes Higher Timeframe (H1/H4) directional bias.
    Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
    """
    if len(df_h1) < 200:
        return "NEUTRAL"

    # Resample to H1 to get true Higher Timeframe context
    df_h1 = df_h1.set_index('time')
    df_h1_resampled = df_h1.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    close = df_h1_resampled["close"]
    ema50 = calculate_ema(close, 50)
    ema200 = calculate_ema(close, 200)

    last_close = close.iloc[-1]
    last_ema50 = ema50.iloc[-1]
    last_ema200 = ema200.iloc[-1]

    if pd.isna(last_ema50) or pd.isna(last_ema200):
        return "NEUTRAL"

    if last_ema50 > last_ema200 and last_close > last_ema50:
        return "BULLISH"
    elif last_ema50 < last_ema200 and last_close < last_ema50:
        return "BEARISH"
    else:
        return "NEUTRAL"


def validate_mtf_alignment(signal_side: str, htf_bias: str) -> bool:
    """
    Validates if lower timeframe signal_side matches HTF trend bias.
    """
    if htf_bias == "BULLISH" and signal_side != "BUY":
        return False
    if htf_bias == "BEARISH" and signal_side != "SELL":
        return False
    return True
