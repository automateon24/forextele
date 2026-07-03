import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\25stragy\config_hybrid_aggressive.json"
try:
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    print("=== Config Keys ===")
    print(list(config.keys()))
    
    # Print the first few keys and values
    for k in list(config.keys())[:8]:
        val = config[k]
        if isinstance(val, dict):
            print(f"\n{k}:")
            for subk in list(val.keys())[:10]:
                print(f"  {subk}: {val[subk]}")
        else:
            print(f"{k}: {val}")
except Exception as e:
    print("Error reading config:", e)
