import json
import subprocess
import re
import os

def run_backtest_with_duration(duration):
    config_path = "C:\\25stragy\\config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)
        
    config["strategy_tuning"]["max_trade_duration_mins"] = duration
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
        
    print(f"\n==================================================")
    print(f"Running backtest with duration = {duration} mins...")
    print(f"==================================================")
    
    proc = subprocess.run(
        ["C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\python.exe", "BACKTEST_V8_AI.py"],
        cwd="C:\\25stragy",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    
    output = proc.stdout
    
    # Parse the summary table from stdout
    trades = 0
    wr = "0%"
    pnl = "Rs.0"
    max_dd = "Rs.0"
    
    # Find Combined Stats
    match_trades = re.search(r"Trades\s+:\s+(\d+)", output)
    match_wr = re.search(r"Win rate\s+:\s+([\d\.]+%)", output)
    match_pnl = re.search(r"Total PnL\s+:\s+(Rs\.[\d,+-]+)", output)
    match_dd = re.search(r"Max drawdown\s+:\s+(Rs\.[\d,+-]+)", output)
    
    if match_trades: trades = int(match_trades.group(1))
    if match_wr: wr = match_wr.group(1)
    if match_pnl: pnl = match_pnl.group(1)
    if match_dd: max_dd = match_dd.group(1)
    
    print(f"Results for {duration} mins:")
    print(f"  Trades      : {trades}")
    print(f"  Win Rate    : {wr}")
    print(f"  Total PnL   : {pnl}")
    print(f"  Max Drawdown: {max_dd}")
    
    return {
        "duration": duration,
        "trades": trades,
        "win_rate": wr,
        "pnl": pnl,
        "max_drawdown": max_dd
    }

def main():
    results = []
    durations = [30, 45, 60, 90]
    
    for d in durations:
        res = run_backtest_with_duration(d)
        results.append(res)
        
    print("\n==================================================")
    print("FINAL scorecard FOR TRADE DURATION EXPERIMENTS")
    print("==================================================")
    print(f"{'Duration':10} | {'Trades':6} | {'Win Rate':8} | {'Total PnL':12} | {'Max Drawdown':12}")
    print("-" * 60)
    for r in results:
        print(f"{r['duration']:<10} | {r['trades']:<6} | {r['win_rate']:<8} | {r['pnl']:<12} | {r['max_drawdown']:<12}")
        
if __name__ == "__main__":
    main()
