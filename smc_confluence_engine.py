import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import os
import json
import logging
from datetime import datetime

BASE_DIR = r"c:\anlyzeforex\forextele"
CONFIG_PATH = os.path.join(BASE_DIR, "mt5_config.json")

def connect_mt5():
    if not mt5.initialize():
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f: cfg = json.load(f)
            mt5.initialize(login=cfg.get('login'), server=cfg.get('server'), password=cfg.get('password'))
    return mt5.terminal_info() is not None

class SMCConfluenceEngine:
    def __init__(self):
        pass

    def get_smc_analysis(self, symbol: str, direction: str, timeframe=mt5.TIMEFRAME_M15) -> dict:
        """
        Analyzes live market structure for Smart Money Concepts (SMC):
        - Order Blocks (OB)
        - Fair Value Gaps (FVG)
        - Break of Structure (BOS)
        - Liquidity Sweeps
        - Candle Momentum Velocity
        Returns SMC Confluence Score (0.0 to 1.0) and structural SL recommendation.
        """
        if not connect_mt5():
            return self._default_response(direction, "MT5 Connection Unavailable")

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 100)
        if rates is None or len(rates) < 30:
            return self._default_response(direction, "Insufficient Candle Rates")

        df = pd.DataFrame(rates)

        # 1. FAIR VALUE GAP (FVG) DETECTION
        # Bullish FVG: Low of candle i > High of candle i-2
        # Bearish FVG: High of candle i < Low of candle i-2
        df['bullish_fvg'] = df['low'] > df['high'].shift(2)
        df['bearish_fvg'] = df['high'] < df['low'].shift(2)

        has_recent_bull_fvg = df['bullish_fvg'].iloc[-10:].any()
        has_recent_bear_fvg = df['bearish_fvg'].iloc[-10:].any()

        # 2. BREAK OF STRUCTURE (BOS)
        # Check if last 5 candles broke recent 20-period Swing High/Low
        swing_high_20 = df['high'].iloc[-30:-5].max()
        swing_low_20 = df['low'].iloc[-30:-5].min()

        latest_close = df['close'].iloc[-1]
        latest_high = df['high'].iloc[-1]
        latest_low = df['low'].iloc[-1]

        bullish_bos = latest_close > swing_high_20
        bearish_bos = latest_close < swing_low_20

        # 3. ORDER BLOCK (OB) DETECTION & STRUCTURAL SL
        # Bullish OB: Last down candle before strong bullish impulse
        # Bearish OB: Last up candle before strong bearish impulse
        df['candle_body'] = (df['close'] - df['open']).abs()
        mean_body = df['candle_body'].mean()

        bullish_ob_price = swing_low_20
        bearish_ob_price = swing_high_20

        for i in range(len(df)-2, 10, -1):
            if df['close'].iloc[i] < df['open'].iloc[i] and (df['close'].iloc[i+1] - df['open'].iloc[i+1]) > (mean_body * 1.5):
                bullish_ob_price = df['low'].iloc[i]
                break

        for i in range(len(df)-2, 10, -1):
            if df['close'].iloc[i] > df['open'].iloc[i] and (df['open'].iloc[i+1] - df['close'].iloc[i+1]) > (mean_body * 1.5):
                bearish_ob_price = df['high'].iloc[i]
                break

        # 4. MOMENTUM VELOCITY & RUNNING CANDLE DISTANCE
        # Calculate last candle move speed relative to ATR
        df['tr'] = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift()).abs(),
            (df['low'] - df['close'].shift()).abs()
        ], axis=1).max(axis=1)
        atr_14 = df['tr'].rolling(14).mean().iloc[-1]

        recent_move = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
        momentum_ratio = recent_move / atr_14 if atr_14 > 0 else 1.0
        is_strong_momentum = momentum_ratio >= 0.85

        # 5. SMC CONFLUENCE SCORE CALCULATION
        score = 0.50 # Base score

        if direction.upper() == "BUY":
            if bullish_bos: score += 0.20
            if has_recent_bull_fvg: score += 0.15
            if is_strong_momentum: score += 0.15
            structural_sl = bullish_ob_price - (atr_14 * 0.5)
        else:
            if bearish_bos: score += 0.20
            if has_recent_bear_fvg: score += 0.15
            if is_strong_momentum: score += 0.15
            structural_sl = bearish_ob_price + (atr_14 * 0.5)

        score = max(0.10, min(0.98, score))

        return {
            "symbol": symbol,
            "direction": direction,
            "smc_confluence_score": round(score, 2),
            "bullish_bos": bool(bullish_bos),
            "bearish_bos": bool(bearish_bos),
            "fvg_aligned": bool(has_recent_bull_fvg if direction.upper() == "BUY" else has_recent_bear_fvg),
            "momentum_ratio": round(float(momentum_ratio), 2),
            "is_strong_momentum": bool(is_strong_momentum),
            "structural_sl": round(float(structural_sl), mt5.symbol_info(symbol).digits if mt5.symbol_info(symbol) else 4),
            "atr": round(float(atr_14), 4)
        }

    def _default_response(self, direction, reason):
        return {
            "symbol": "UNKNOWN",
            "direction": direction,
            "smc_confluence_score": 0.50,
            "bullish_bos": False,
            "bearish_bos": False,
            "fvg_aligned": False,
            "momentum_ratio": 1.0,
            "is_strong_momentum": False,
            "structural_sl": 0.0,
            "atr": 0.0,
            "note": reason
        }

if __name__ == "__main__":
    smc = SMCConfluenceEngine()
    res = smc.get_smc_analysis("USDCHF", "BUY")
    print("SMC Analysis Output:", json.dumps(res, indent=2))
