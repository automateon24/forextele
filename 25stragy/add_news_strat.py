import json
from pathlib import Path

dna_path = Path(r"c:\anlyzeforex\forextele\25stragy\forex_strategy_dna.json")

with open(dna_path, "r") as f:
    data = json.load(f)

data["strategies"]["NEWS_BREAKOUT_STRADDLE"] = {
    "direction": "BOTH",
    "entry_start": 0,    # Triggered dynamically by calendar API, not static time
    "entry_end": 2359,
    "require_vwap": False,
    "require_volume": False,
    "direction_bias": "STRADDLE", # Indicates simultaneous pending orders (Buy Stop/Sell Stop)
    "tsl_a": 0.05,
    "tsl_t": 0.03,
    "tgt": 2.0,       # High target to capture massive spikes (e.g. NFP, CPI)
    "sl": 0.15,       # Tight SL on the straddle legs
    "thresh": 0.95,
    "max_d": 1,
    "min_p": 10,
    "max_p": 200,
    "boost": 0.1,
    "straddle_gap_pips": 10  # Placed 10 pips above/below current price before news
}

data["strategy_regime_matrix"]["NEWS_BREAKOUT_STRADDLE"] = {
    "TRENDING_BULL": True,
    "TRENDING_BEAR": True,
    "RANGE_BOUND": False,
    "HIGH_VOLATILITY": True, # The primary regime
    "NORMAL": False
}

with open(dna_path, "w") as f:
    json.dump(data, f, indent=2)

print("NEWS_BREAKOUT_STRADDLE added successfully.")
