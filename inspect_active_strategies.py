import json
import os
from pathlib import Path

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
DNA_PATH = BASE_DIR / "25stragy" / "ai_optimized_forex_dna.json"
FALLBACK_DNA_PATH = BASE_DIR / "strategy_dna.json"

def inspect_dna():
    print("=" * 80)
    print("  AUTOMATED BOT STRATEGIES SCANNING MATRIX AUDIT")
    print("=" * 80)

    target_path = DNA_PATH if DNA_PATH.exists() else FALLBACK_DNA_PATH
    if not target_path.exists():
        print("[ERROR] Strategy DNA JSON file not found.")
        return

    with open(target_path, 'r') as f:
        data = json.load(f)

    strats = data.get("strategies", {})
    if isinstance(data, list):
        strats = {item.get("name", f"Strat_{i}"): item for i, item in enumerate(data)}

    total_strats = len(strats)
    print(f"\nTOTAL AUTOMATED STRATEGIES IN DNA FILE : {total_strats} Strategies")

    # Multi-timeframe pair matrix from live_strategy_executor.py
    pair_tf_matrix = {
        "GOLD": ("M5", "Active - 5-min High Frequency Scalping"),
        "USDCHF": ("M30", "Active - 30-min Trend Swing (96.6% WR Star Performer)"),
        "GBPJPY": ("M15", "Active - 15-min Volatility Breakout (68.1% WR)"),
        "SILVER": ("M15", "Active - 15-min Metal Swing (Spread Protected)"),
        "AUDUSD": ("M15", "Active - 15-min Major Trend"),
        "USDJPY": ("M15", "Active - 15-min Yen Breakout"),
        "GBPUSD": ("M15", "Active - 15-min Cable Trend"),
        "BTCUSD": ("M15", "Active - 15-min Crypto Momentum (Restricted Lot 0.05 + ML 68% Veto)"),
        "ETHUSD": ("M5", "Active - 5-min Crypto Scalp (Restricted Lot 0.05 + ML 68% Veto)")
    }

    print(f"\nACTIVE MULTI-TIMEFRAME PAIR MATRIX ({len(pair_tf_matrix)} Pairs):")
    print(f"  {'Symbol':<10} | {'Timeframe':<10} | Scan Status & Strategy Performance")
    print(f"  {'-'*70}")
    for sym, (tf, status) in pair_tf_matrix.items():
        print(f"  {sym:<10} | {tf:<10} | {status}")

    print(f"\n" + "=" * 80)
    print(f"  LIST OF ALL {total_strats} AUTOMATED STRATEGIES RUNNING ON EACH ACTIVE PAIR:")
    print(f"  {'#':<4} | {'Strategy Name':<30} | {'Backtest WR':<12} | Primary Indicator Core")
    print(f"  {'-'*75}")

    for idx, (s_name, s_info) in enumerate(strats.items(), 1):
        wr = s_info.get("win_rate", s_info.get("wr", 0.0))
        if isinstance(wr, float) and wr <= 1.0: wr = wr * 100
        desc = s_info.get("description", s_info.get("type", "Technical Indicator Confluence"))
        print(f"  {idx:<4} | {s_name[:30]:<30} | {wr:>5.1f}%      | {desc[:30]}")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    inspect_dna()
