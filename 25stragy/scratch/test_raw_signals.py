import shutil
import os
import subprocess

# 18 Target strategies (Disabled, Not Triggered, Underperforming)
target_strats = [
    'BREAKOUT', 'MORNING_BREAKOUT', 'LONG_UNWIND', 'RESIST_BREAK', 
    'TREND_FOLLOWING', 'OPENING_DRIVE', 'PREMIUM_CRUSH',
    'MEAN_REVERSION', 'VOLATILITY_BREAKOUT', 'EARLY_BREAKDOWN', 
    'BULL_TREND_FOLLOWER', 'ORDER_BLOCK_REVERSAL', 'WIDE_RANGE_RIDER', 
    'SHORT_UNWIND', 'ENHANCED_BEARISH', 'DAY_HIGH_LOW_TRADITIONAL',
    'AI_ENHANCED', 'PUT_WRITER_SUPPORT'
]

# Backup original files
shutil.copy(r'C:\25stragy\BACKTEST_V8_AI.py', r'C:\25stragy\BACKTEST_V8_AI.py.tmp')
shutil.copy(r'C:\25stragy\config.json', r'C:\25stragy\config.json.tmp')

try:
    # 1. Modify config.json to run ONLY the 18 target strategies
    import json
    with open(r'C:\25stragy\config.json', 'r') as f:
        config = json.load(f)
    for idx in config['index_profiles']:
        config['index_profiles'][idx]['active_strategies'] = target_strats
    with open(r'C:\25stragy\config.json', 'w') as f:
        json.dump(config, f, indent=2)

    # 2. Modify BACKTEST_V8_AI.py to bypass match_profile for target_strats
    with open(r'C:\25stragy\BACKTEST_V8_AI.py', 'r') as f:
        code = f.read()

    # Locate the match_profile call block and inject bypass
    target_block = """                    profile = idx_profiles[strat.name]
                    armed, conf, arm_reason = match_profile(profile, ctx, state, direction)"""
    
    replacement_block = """                    profile = idx_profiles[strat.name]
                    target_strats = [
                        'BREAKOUT', 'MORNING_BREAKOUT', 'LONG_UNWIND', 'RESIST_BREAK', 
                        'TREND_FOLLOWING', 'OPENING_DRIVE', 'PREMIUM_CRUSH',
                        'MEAN_REVERSION', 'VOLATILITY_BREAKOUT', 'EARLY_BREAKDOWN', 
                        'BULL_TREND_FOLLOWER', 'ORDER_BLOCK_REVERSAL', 'WIDE_RANGE_RIDER', 
                        'SHORT_UNWIND', 'ENHANCED_BEARISH', 'DAY_HIGH_LOW_TRADITIONAL',
                        'AI_ENHANCED', 'PUT_WRITER_SUPPORT'
                    ]
                    if strat.name in target_strats:
                        armed = True
                        conf = 0.85
                        arm_reason = "Bypassed profile check"
                    else:
                        armed, conf, arm_reason = match_profile(profile, ctx, state, direction)"""

    if target_block in code:
        code = code.replace(target_block, replacement_block)
        print("Successfully injected bypass code into BACKTEST_V8_AI.py")
    else:
        # Try variation with different spacing
        print("Warning: Target block not matched exactly, attempting line replacement...")
        code_lines = code.split('\n')
        replaced = False
        for idx_l, line in enumerate(code_lines):
            if 'armed, conf, arm_reason = match_profile' in line:
                code_lines[idx_l] = """                    target_strats = ['BREAKOUT', 'MORNING_BREAKOUT', 'LONG_UNWIND', 'RESIST_BREAK', 'TREND_FOLLOWING', 'OPENING_DRIVE', 'PREMIUM_CRUSH', 'MEAN_REVERSION', 'VOLATILITY_BREAKOUT', 'EARLY_BREAKDOWN', 'BULL_TREND_FOLLOWER', 'ORDER_BLOCK_REVERSAL', 'WIDE_RANGE_RIDER', 'SHORT_UNWIND', 'ENHANCED_BEARISH', 'DAY_HIGH_LOW_TRADITIONAL', 'AI_ENHANCED', 'PUT_WRITER_SUPPORT']
                    if strat.name in target_strats:
                        armed = True
                        conf = 0.85
                        arm_reason = "Bypassed profile check"
                    else:
                        """ + line.strip()
                replaced = True
                break
        if replaced:
            code = '\n'.join(code_lines)
            print("Successfully patched line-by-line.")
        else:
            raise Exception("Failed to find match_profile call in code")

    with open(r'C:\25stragy\BACKTEST_V8_AI.py', 'w') as f:
        f.write(code)

    print("Patched files. Starting raw signal backtest...")
    
    # Run backtest
    result = subprocess.run(
        [r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe', r'C:\25stragy\BACKTEST_V8_AI.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors='ignore'
    )
    
    with open(r'C:\25stragy\scratch\raw_signals_backtest_out.txt', 'w') as f:
        f.write(result.stdout)
        f.write("\n=== STDERR ===\n")
        f.write(result.stderr)

    print("Raw signal backtest completed.")

finally:
    # Restore original files
    shutil.copy(r'C:\25stragy\BACKTEST_V8_AI.py.tmp', r'C:\25stragy\BACKTEST_V8_AI.py')
    shutil.copy(r'C:\25stragy\config.json.tmp', r'C:\25stragy\config.json')
    if os.path.exists(r'C:\25stragy\BACKTEST_V8_AI.py.tmp'):
        os.remove(r'C:\25stragy\BACKTEST_V8_AI.py.tmp')
    if os.path.exists(r'C:\25stragy\config.json.tmp'):
        os.remove(r'C:\25stragy\config.json.tmp')

# Print statistics of the raw run
print("\n--- RESULTS OF ISOLATED BACKTEST WITHOUT AI PROFILE FILTERS ---")
subprocess.run([r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe', r'C:\25stragy\scratch\audit_strats.py'])
