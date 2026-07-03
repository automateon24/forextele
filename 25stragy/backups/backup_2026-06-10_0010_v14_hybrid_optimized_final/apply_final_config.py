import json
import subprocess

# Define the final optimized 23-strategy suite
optimized_23 = [
    # 17 Original Profitable (excluding ENHANCED_BULLISH)
    "ZERO_HERO", "BEAR_TREND_FOLLOWER", "MACD_DIVERGENCE", "MOMENTUM_BURST",
    "VWAP_BOUNCE", "GAMMA_BLAST", "OPTIONS_GREEKS", "SCALPING", "MAGIC_SQUARE",
    "BOLLINGER_SQUEEZE", "ATR_BREAK", "ULTIMATE_DAY_HIGH_LOW", "DAY_LOW_BULLISH",
    "EMA_CROSSOVER", "VOLUME_CLIMAX", "RSI_REVERSAL", "DAY_HIGH_BEARISH",
    # 6 Newly enabled & optimized profitable (excluding SHORT_UNWIND)
    "LONG_UNWIND", "TREND_FOLLOWING", "PUT_WRITER_SUPPORT", "AI_ENHANCED",
    "BREAKOUT", "RESIST_BREAK"
]

# Load and update config.json
config_path = r'C:\25stragy\config.json'
with open(config_path, 'r') as f:
    config = json.load(f)

for idx in config['index_profiles']:
    config['index_profiles'][idx]['active_strategies'] = optimized_23
    print(f"Set final active strategies for {idx} to 23-strategy suite.")

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

print("Running final verification backtest...")

# Run BACKTEST_V8_AI.py
result = subprocess.run(
    [r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe', r'C:\25stragy\BACKTEST_V8_AI.py'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    errors='ignore'
)

# Save log
with open(r'C:\25stragy\scratch\final_verification_out.txt', 'w') as f:
    f.write(result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr)

print("Final verification backtest completed.")
