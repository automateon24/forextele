import json
import subprocess

# Define the 25 profitable strategies
active_25 = [
    # 18 Original Profitable
    "ZERO_HERO", "BEAR_TREND_FOLLOWER", "MACD_DIVERGENCE", "MOMENTUM_BURST",
    "VWAP_BOUNCE", "GAMMA_BLAST", "OPTIONS_GREEKS", "SCALPING", "MAGIC_SQUARE",
    "BOLLINGER_SQUEEZE", "ATR_BREAK", "ULTIMATE_DAY_HIGH_LOW", "DAY_LOW_BULLISH",
    "EMA_CROSSOVER", "VOLUME_CLIMAX", "RSI_REVERSAL", "DAY_HIGH_BEARISH", "ENHANCED_BULLISH",
    # 7 Newly enabled & optimized profitable
    "LONG_UNWIND", "TREND_FOLLOWING", "PUT_WRITER_SUPPORT", "AI_ENHANCED",
    "BREAKOUT", "RESIST_BREAK", "SHORT_UNWIND"
]

# Update config.json
config_path = r'C:\25stragy\config.json'
with open(config_path, 'r') as f:
    config = json.load(f)

for idx in config['index_profiles']:
    config['index_profiles'][idx]['active_strategies'] = active_25
    print(f"Set active strategies for {idx} to 25-strategy suite.")

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

print("Starting combined backtest...")

# Run BACKTEST_V8_AI.py
result = subprocess.run(
    [r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe', r'C:\25stragy\BACKTEST_V8_AI.py'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    errors='ignore'
)

# Save log
with open(r'C:\25stragy\scratch\combined_backtest_out.txt', 'w') as f:
    f.write(result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr)

print("Combined backtest completed.")
