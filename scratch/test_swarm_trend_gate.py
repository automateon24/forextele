import sys
from pathlib import Path
BASE_DIR = Path(r"C:\anlyzeforex\forextele")
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import asyncio
import MetaTrader5 as mt5
mt5.initialize()

from ai_conviction_tsl_manager import get_channel_conviction

print("=== CHANNEL CONVICTION CALIBRATION TEST ===")
test_channels = [
    "Swich Gold Forex",
    "Market Trader Crypto Forex",
    "JOSEFINA TRADER0",
    "Gold VIP",
    "SureShot GOLD",
    "Vault Gold Forex",
    "RIAOGOLDFOREX",
    "DUBAI CAPITAL FX"
]

for ch in test_channels:
    conv = get_channel_conviction(ch)
    tier = "ELITE TIER 1 (>= 0.85)" if conv >= 0.85 else "STANDARD / GATED (< 0.85)"
    print(f"{ch:28} | Conviction: {conv:.2f} | {tier}")

# Check live H1 Trend
rates = mt5.copy_rates_from_pos("GOLD", mt5.TIMEFRAME_H1, 0, 100)
if rates is not None and len(rates) >= 50:
    import pandas as pd
    df_h1 = pd.DataFrame(rates)
    ema50 = df_h1['close'].ewm(span=50).mean().iloc[-2]
    ema200 = df_h1['close'].ewm(span=200).mean().iloc[-2]
    latest_c = df_h1['close'].iloc[-2]
    h1_is_bearish = (latest_c < ema50 and ema50 < ema200)
    h1_is_bullish = (latest_c > ema50 and ema50 > ema200)
    print(f"\nLive GOLD H1 Macro Trend: {'BEARISH' if h1_is_bearish else ('BULLISH' if h1_is_bullish else 'NEUTRAL')}")
    print(f"Price: {latest_c:.2f} | EMA50: {ema50:.2f} | EMA200: {ema200:.2f}")
    
    print("\n=== HYPOTHETICAL SIGNAL GATE EVALUATION ===")
    for ch in ["RIAOGOLDFOREX", "Swich Gold Forex"]:
        c = get_channel_conviction(ch)
        # Test BUY
        if c < 0.85 and h1_is_bearish:
            print(f"[TEST 1] {ch} BUY GOLD -> ❌ VETOED (Counter-trend BUY blocked during H1 BEARISH)")
        else:
            print(f"[TEST 1] {ch} BUY GOLD -> ✅ APPROVED (Elite channel or trend aligned)")
            
        # Test SELL
        if c < 0.85 and h1_is_bullish:
            print(f"[TEST 2] {ch} SELL GOLD -> ❌ VETOED")
        else:
            print(f"[TEST 2] {ch} SELL GOLD -> ✅ APPROVED (Trend-aligned SELL during H1 BEARISH)")

mt5.shutdown()
