import json
import subprocess
import os

# Define combinations to test
combinations = [
    # 1. Base 25
    {
        "name": "Base 25-Strategy Suite",
        "exclude": []
    },
    # 2. Exclude ENHANCED_BULLISH
    {
        "name": "Exclude ENHANCED_BULLISH",
        "exclude": ["ENHANCED_BULLISH"]
    },
    # 3. Exclude SHORT_UNWIND
    {
        "name": "Exclude SHORT_UNWIND",
        "exclude": ["SHORT_UNWIND"]
    },
    # 4. Exclude BOTH ENHANCED_BULLISH & SHORT_UNWIND
    {
        "name": "Exclude BOTH ENHANCED_BULLISH & SHORT_UNWIND",
        "exclude": ["ENHANCED_BULLISH", "SHORT_UNWIND"]
    },
    # 5. Exclude ENHANCED_BULLISH, SHORT_UNWIND & AI_ENHANCED
    {
        "name": "Exclude ENHANCED_BULLISH, SHORT_UNWIND & AI_ENHANCED",
        "exclude": ["ENHANCED_BULLISH", "SHORT_UNWIND", "AI_ENHANCED"]
    }
]

base_25 = [
    "ZERO_HERO", "BEAR_TREND_FOLLOWER", "MACD_DIVERGENCE", "MOMENTUM_BURST",
    "VWAP_BOUNCE", "GAMMA_BLAST", "OPTIONS_GREEKS", "SCALPING", "MAGIC_SQUARE",
    "BOLLINGER_SQUEEZE", "ATR_BREAK", "ULTIMATE_DAY_HIGH_LOW", "DAY_LOW_BULLISH",
    "EMA_CROSSOVER", "VOLUME_CLIMAX", "RSI_REVERSAL", "DAY_HIGH_BEARISH", "ENHANCED_BULLISH",
    "LONG_UNWIND", "TREND_FOLLOWING", "PUT_WRITER_SUPPORT", "AI_ENHANCED",
    "BREAKOUT", "RESIST_BREAK", "SHORT_UNWIND"
]

config_path = r'C:\25stragy\config.json'
with open(config_path, 'r') as f:
    orig_config = json.load(f)

results = []

try:
    for idx_c, combo in enumerate(combinations):
        print(f"\n--- TESTING COMBO {idx_c+1}: {combo['name']} ---")
        
        # Calculate active strategies
        active = [s for s in base_25 if s not in combo['exclude']]
        
        # Update config.json
        for idx in orig_config['index_profiles']:
            orig_config['index_profiles'][idx]['active_strategies'] = active
        with open(config_path, 'w') as f:
            json.dump(orig_config, f, indent=2)
            
        # Run backtest
        res = subprocess.run(
            [r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe', r'C:\25stragy\BACKTEST_V8_AI.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors='ignore'
        )
        
        # Parse PnL and Max DD from stdout
        pnl = 0.0
        max_dd = 0.0
        avg_pnl_day = 0.0
        trades = 0
        win_rate = 0.0
        
        stdout_lines = res.stdout.split('\n')
        for line in stdout_lines:
            if 'Trades             :' in line:
                try: trades = int(line.split(':')[1].strip())
                except: pass
            if 'Win rate           :' in line:
                try: win_rate = float(line.split(':')[1].replace('%', '').strip())
                except: pass
            if 'Total PnL          :' in line:
                try: pnl = float(line.split(':')[1].replace('Rs.', '').replace(',', '').strip())
                except: pass
            if 'Avg PnL/day        :' in line:
                try: avg_pnl_day = float(line.split(':')[1].split('(')[0].replace('Rs.', '').replace(',', '').strip())
                except: pass
            if 'Max drawdown       :' in line:
                try: max_dd = float(line.split(':')[1].replace('Rs.', '').replace(',', '').strip())
                except: pass
                
        print(f"PnL: Rs. {pnl:+,} | Trades: {trades} | WR: {win_rate}% | Avg/Day: Rs. {avg_pnl_day:+,} | Max DD: Rs. {max_dd:,}")
        results.append({
            "combo": combo['name'],
            "exclude": combo['exclude'],
            "pnl": pnl,
            "trades": trades,
            "win_rate": win_rate,
            "avg_pnl_day": avg_pnl_day,
            "max_dd": max_dd
        })

finally:
    # Restore original config.json
    with open(config_path, 'w') as f:
        json.dump(orig_config, f, indent=2)

print("\n=== SUMMARY OF PRUNING COMBINATIONS ===")
for r in results:
    print(f"{r['combo']}:")
    print(f"  Total PnL: Rs. {r['pnl']:+,}")
    print(f"  Trades: {r['trades']} | Win Rate: {r['win_rate']}%")
    print(f"  Avg PnL/Day: Rs. {r['avg_pnl_day']:+,}")
    print(f"  Max Drawdown: Rs. {r['max_dd']:,}")
