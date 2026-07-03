import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open(r"C:\25stragy\config_hybrid_aggressive.json", "r") as f:
    config = json.load(f)

with open(r"C:\25stragy\strategy_dna.json", "r") as f:
    dna = json.load(f)

print("=== Config Index Profiles ===")
for k, v in config.get("index_profiles", {}).items():
    print(f"Index: {k}, Lot Size: {v.get('lot_size')}, ATM Step: {v.get('atm_step')}")

print("\n=== Strategy DNA Strikes ===")
for k, v in dna.get("strategies", {}).items():
    print(f"Strategy: {k}, Strike: {v.get('strike')}")
