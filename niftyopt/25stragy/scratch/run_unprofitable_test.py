import json
import shutil
import subprocess
import os

# Backup config.json
shutil.copy(r'C:\25stragy\config.json', r'C:\25stragy\config.json.tmp')

try:
    # Load config
    with open(r'C:\25stragy\config.json', 'r') as f:
        config = json.load(f)

    # 18 Target strategies (Disabled, Not Triggered, Underperforming)
    target_strats = [
        'BREAKOUT', 'MORNING_BREAKOUT', 'LONG_UNWIND', 'RESIST_BREAK', 
        'TREND_FOLLOWING', 'OPENING_DRIVE', 'PREMIUM_CRUSH',
        'MEAN_REVERSION', 'VOLATILITY_BREAKOUT', 'EARLY_BREAKDOWN', 
        'BULL_TREND_FOLLOWER', 'ORDER_BLOCK_REVERSAL', 'WIDE_RANGE_RIDER', 
        'SHORT_UNWIND', 'ENHANCED_BEARISH', 'DAY_HIGH_LOW_TRADITIONAL',
        'AI_ENHANCED', 'PUT_WRITER_SUPPORT'
    ]

    # Set active_strategies to target_strats for all indices
    for idx in config['index_profiles']:
        config['index_profiles'][idx]['active_strategies'] = target_strats

    # Save temporary config
    with open(r'C:\25stragy\config.json', 'w') as f:
        json.dump(config, f, indent=2)

    print("Configured config.json to run ONLY the 18 target strategies. Starting backtest...")
    
    # Run BACKTEST_V8_AI.py and wait for it to complete
    result = subprocess.run(
        [r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe', r'C:\25stragy\BACKTEST_V8_AI.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors='ignore'
    )
    
    # Save log
    with open(r'C:\25stragy\scratch\unprofitable_backtest_out.txt', 'w') as f:
        f.write(result.stdout)
        f.write("\n=== STDERR ===\n")
        f.write(result.stderr)

    print("Backtest completed. Restoring original config.json...")

finally:
    # Restore original config.json
    shutil.copy(r'C:\25stragy\config.json.tmp', r'C:\25stragy\config.json')
    if os.path.exists(r'C:\25stragy\config.json.tmp'):
        os.remove(r'C:\25stragy\config.json.tmp')

# Run audit script to print statistics of interest
print("\n--- RESULTS OF ISOLATED BACKTEST ON THE 18 TARGET STRATEGIES ---")
subprocess.run([r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe', r'C:\25stragy\scratch\audit_strats.py'])
