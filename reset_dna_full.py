import json

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "GOLD", "SILVER", "BTCUSD", "ETHUSD"]

STRATEGIES = [
    "ZERO_HERO", "ASIAN_RANGE_SCALP", "LONDON_BREAKOUT", "NY_MOMENTUM",
    "TREND_RIDER", "MEAN_REVERSION", "ORDER_BLOCK_REVERSAL", "INSTITUTIONAL_SUPPORT",
    "MAGIC_SQUARE", "VOLUME_CLIMAX", "AI_ENHANCED", "SCALPING", "PIP_BLAST",
    "SWAP_ARBITRAGE", "WIDE_RANGE_RIDER", "NARROW_RANGE_BREAKOUT", "FRACTAL_TREND",
    "MACD_DIVERGENCE", "RSI_OVEREXTENDED", "BOLLINGER_SQUEEZE", "ICHIMOKU_CLOUD",
    "VWAP_PULLBACK", "FIBONACCI_RETRACEMENT", "GARTLEY_PATTERN", "ELLIOTT_WAVE",
    "MOVING_AVERAGE_CROSS", "STOCHASTIC_OSCILLATOR", "CCI_TREND", "PARABOLIC_SAR",
    "HEIKIN_ASHI_TREND", "RENKO_BRICKS", "POINT_AND_FIGURE", "MARKET_PROFILE",
    "TPO_VALUE_AREA", "FOOTPRINT_IMBALANCE", "DELTA_DIVERGENCE", "CUMULATIVE_DELTA",
    "OPEN_INTEREST", "FUNDING_RATE", "LIQUIDATION_HUNT", "ENHANCED_BEARISH"
]

dna_db = {"strategies": {}}

for pair in PAIRS:
    for strat in STRATEGIES:
        key = f"{pair}_{strat}"
        dna_db["strategies"][key] = {
            "sl": 1.0,
            "tgt": 3.0,
            "use_grid": False
        }

with open("25stragy/ai_optimized_forex_dna.json", "w") as f:
    json.dump(dna_db, f, indent=4)
    
print(f"Restored {len(dna_db['strategies'])} full combinations in DNA.")
