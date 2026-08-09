import re

with open('live_strategy_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix the base_dna to use the 'strategies' key if present
if 'base_dna.get("strategies"' not in code:
    code = code.replace(
        'symbol_dnas = {k: v for k, v in base_dna.items() if k.startswith(f"{dna_symbol_key}:")}',
        'strategies_dict = base_dna.get("strategies", base_dna)\n            symbol_dnas = {k: v for k, v in strategies_dict.items() if k.startswith(f"{dna_symbol_key}_")}'
    )

# Fix the split logic
if 'sn = strat_key.split("_", 1)[1]' not in code:
    code = code.replace(
        'sn = strat_key.split(":")[1]',
        'sn = strat_key.split("_", 1)[1]'
    )

with open('live_strategy_executor.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Fixed symbol_dnas extraction!")
