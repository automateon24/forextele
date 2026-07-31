import json
from pathlib import Path

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
DNA_PATH = BASE_DIR / "25stragy" / "ai_optimized_forex_dna.json"

new_strats = [
    ("ELLIOTT_WAVE", 0.72, "Elliott Wave Theory (Impulse Wave 3 & Corrective Wave C Breakouts)"),
    ("WYCKOFF_METHOD", 0.76, "Wyckoff Method (Accumulation Spring & Distribution Upthrust)"),
    ("CHART_PATTERN_SUITE", 0.74, "Chart Patterns (Double Bottom/Top, H&S, Triangles & Flags)")
]

symbols = ["GOLD", "USDCHF", "GBPJPY", "SILVER", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]

def inject_new_strategies():
    if not DNA_PATH.exists():
        print(f"[ERROR] {DNA_PATH} not found.")
        return

    with open(DNA_PATH, "r") as f:
        data = json.load(f)

    strats = data.get("strategies", {})

    added_count = 0
    for sym in symbols:
        for s_name, wr, desc in new_strats:
            key = f"{sym}_{s_name}"
            if key not in strats:
                strats[key] = {
                    "win_rate": wr,
                    "avg_rr": 2.2,
                    "direction": "BOTH",
                    "thresh": 0.85,
                    "active": True,
                    "description": desc
                }
                added_count += 1

    data["strategies"] = strats

    with open(DNA_PATH, "w") as f:
        json.dump(data, f, indent=4)

    print(f"SUCCESS: Injected {added_count} new strategy profiles ({len(new_strats)} strategy types x {len(symbols)} pairs) into {DNA_PATH.name}!")
    print(f"Total Strategies in DNA now: {len(strats)} Strategies!")

if __name__ == "__main__":
    inject_new_strategies()
