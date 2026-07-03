import json
import re

# 1. Update strategy_dna.json
dna_path = r'C:\25stragy\strategy_dna.json'
with open(dna_path, 'r') as f:
    dna = json.load(f)

# Update TREND_FOLLOWING entry_end to 1430
if 'TREND_FOLLOWING' in dna['strategies']:
    dna['strategies']['TREND_FOLLOWING']['entry_end'] = 1430
    print("Updated TREND_FOLLOWING entry_end to 1430 in strategy_dna.json")

with open(dna_path, 'w') as f:
    json.dump(dna, f, indent=2)

# 2. Update config.json to enable the 7 disabled strategies
config_path = r'C:\25stragy\config.json'
with open(config_path, 'r') as f:
    config = json.load(f)

disabled_strats = ['BREAKOUT', 'MORNING_BREAKOUT', 'LONG_UNWIND', 'RESIST_BREAK', 'TREND_FOLLOWING', 'OPENING_DRIVE', 'PREMIUM_CRUSH']

for idx in config['index_profiles']:
    active = config['index_profiles'][idx]['active_strategies']
    # Add if not present
    for ds in disabled_strats:
        if ds not in active:
            active.append(ds)
    print(f"Enabled disabled strategies for {idx}")

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

# 3. Modify BACKTEST_V8_AI.py
engine_path = r'C:\25stragy\BACKTEST_V8_AI.py'
with open(engine_path, 'r') as f:
    code = f.read()

# Fix 1: len(candles15) < 3 check for OPENING_DRIVE
target_len = "    if len(candles15) < 3:\n        return False"
replacement_len = "    if len(candles15) < (2 if strat.name == 'OPENING_DRIVE' else 3):\n        return False"
if target_len in code:
    code = code.replace(target_len, replacement_len)
    print("Patched len(candles15) check for OPENING_DRIVE")

# Fix 2: remove hardcoded TREND_FOLLOWING and SHORT_UNWIND block in signal_check_idx
target_block = """    # Remove hardcoded tiered cutoffs and let strategy_dna.json's entry_start / entry_end govern.
    # We only disable explicitly unwanted strategies.
    if strat.name in {'TREND_FOLLOWING', 'SHORT_UNWIND'}:
        return False"""
if target_block in code:
    code = code.replace(target_block, "    # Remove hardcoded tiered cutoffs and let strategy_dna.json's entry_start / entry_end govern.")
    print("Removed hardcoded rejections of TREND_FOLLOWING and SHORT_UNWIND")

# Fix 3: replace hardcoded cutoff = 1300 with strat.entry_end
target_cutoff = """    # Standard cutoff override for expiry ZERO_HERO/GAMMA_BLAST (can run till 15:00)
    cutoff = 1300
    if strat.name in {'GAMMA_BLAST', 'ZERO_HERO'} and expiry:
        cutoff = 1500"""

replacement_cutoff = """    # Standard cutoff override for expiry ZERO_HERO/GAMMA_BLAST (can run till 15:00)
    cutoff = strat.entry_end
    if strat.name in {'GAMMA_BLAST', 'ZERO_HERO'} and expiry:
        cutoff = max(cutoff, 1500)"""
if target_cutoff in code:
    code = code.replace(target_cutoff, replacement_cutoff)
    print("Patched hardcoded cutoff to use strat.entry_end")

# Fix 4: fix bb_position_filter to use the threshold argument
target_bb = """        upper = sma20 + (std20 * 2)
        lower = sma20 - (std20 * 2)"""
replacement_bb = """        upper = sma20 + (std20 * threshold)
        lower = sma20 - (std20 * threshold)"""
if target_bb in code:
    code = code.replace(target_bb, replacement_bb)
    print("Fixed bb_position_filter to use threshold parameter")

# Fix 5: fix VOLATILITY_BREAKOUT contradictory RSI checks
target_vol_bo = """    elif n == 'VOLATILITY_BREAKOUT':
        if d == 'PE':
            return (candle_rng >= avg5_rng * 1.3 and c['close'] < c['open'] and c['close'] < p['low'] and rsi > 52)
        if d == 'CE':
            return (candle_rng >= avg5_rng * 1.3 and c['close'] > c['open'] and c['close'] > p['high'] and rsi < 48)"""

replacement_vol_bo = """    elif n == 'VOLATILITY_BREAKOUT':
        if d == 'PE':
            return (candle_rng >= avg5_rng * 1.3 and c['close'] < c['open'] and c['close'] < p['low'] and rsi < 48)
        if d == 'CE':
            return (candle_rng >= avg5_rng * 1.3 and c['close'] > c['open'] and c['close'] > p['high'] and rsi > 52)"""
if target_vol_bo in code:
    code = code.replace(target_vol_bo, replacement_vol_bo)
    print("Fixed VOLATILITY_BREAKOUT RSI conditions")

with open(engine_path, 'w') as f:
    f.write(code)
print("Finished modifying BACKTEST_V8_AI.py")
